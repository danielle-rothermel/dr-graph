from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Never

import pytest

from dr_graph import (
    GraphRunInterruptedError,
    GraphRunResult,
    GraphRunStatus,
    NodeConfig,
    NodeError,
    NodeOutcome,
    NodeOutcomeStatus,
    NodeOutput,
    TerminalError,
    execute_graph,
    graph_hash,
)
from tests.support import _graph, _node, _output, failure_state_cases


def _raise(error: BaseException) -> Never:
    raise error


def test_result_json_dump_is_persistable_shape() -> None:
    graph = _graph(_node("direct"), terminal_node_id="direct")

    result = execute_graph(
        graph=graph,
        inputs={},
        run_node=lambda node, inputs: _output("ok", field="output"),
    )

    assert result.model_dump(mode="json") == {
        "graph_hash": graph_hash(graph),
        "external_inputs": {},
        "status": "success",
        "outcomes": {
            "direct": {
                "node_id": "direct",
                "status": "success",
                "output": {"values": {"output": "ok"}, "metadata": {}},
                "error": None,
                "blocked_by": [],
                "outcome_source": "fresh",
            }
        },
        "execution_order": ["direct"],
        "terminal_node_id": "direct",
        "terminal_output": "ok",
        "terminal_error": None,
    }


def test_error_outcome_json_dump_is_persistable_shape() -> None:
    graph = _graph(_node("direct"), terminal_node_id="direct")

    result = execute_graph(
        graph=graph,
        inputs={},
        run_node=lambda node, inputs: _raise(RuntimeError("boom")),
    )

    outcome = result.outcomes["direct"]
    assert outcome.error is not None
    dumped = result.model_dump(mode="json")
    assert dumped["outcomes"]["direct"]["error"]["traceback"]
    dumped["outcomes"]["direct"]["error"]["traceback"] = ""
    assert dumped["terminal_error"]["error"]["traceback"]
    dumped["terminal_error"]["error"]["traceback"] = ""
    assert dumped == {
        "graph_hash": graph_hash(graph),
        "external_inputs": {},
        "status": "error",
        "outcomes": {
            "direct": {
                "node_id": "direct",
                "status": "error",
                "output": None,
                "error": {
                    "error_type": (
                        f"{RuntimeError.__module__}."
                        f"{RuntimeError.__qualname__}"
                    ),
                    "message": "boom",
                    "failure_class": None,
                    "metadata": {},
                    "traceback": "",
                },
                "blocked_by": [],
                "outcome_source": "fresh",
            }
        },
        "execution_order": ["direct"],
        "terminal_node_id": "direct",
        "terminal_output": None,
        "terminal_error": {
            "node_id": "direct",
            "status": "error",
            "error": {
                "error_type": (
                    f"{RuntimeError.__module__}.{RuntimeError.__qualname__}"
                ),
                "message": "boom",
                "failure_class": None,
                "metadata": {},
                "traceback": "",
            },
            "blocked_by": [],
        },
    }


def test_blocked_outcome_json_dump_is_persistable_shape() -> None:
    graph = _graph(
        _node("encoder", input_sources={"prompt": "task.prompt"}),
        _node("decoder", input_sources={"description": "encoder"}),
        terminal_node_id="decoder",
    )

    result = execute_graph(
        graph=graph,
        inputs={"prompt": "write f"},
        run_node=lambda node, inputs: _raise(RuntimeError("encoder failed")),
    )

    dumped = result.model_dump(mode="json")
    assert dumped["outcomes"]["encoder"]["error"]["traceback"]
    dumped["outcomes"]["encoder"]["error"]["traceback"] = ""
    assert dumped == {
        "graph_hash": graph_hash(graph),
        "external_inputs": {"prompt": "write f"},
        "status": "blocked",
        "outcomes": {
            "encoder": {
                "node_id": "encoder",
                "status": "error",
                "output": None,
                "error": {
                    "error_type": (
                        f"{RuntimeError.__module__}."
                        f"{RuntimeError.__qualname__}"
                    ),
                    "message": "encoder failed",
                    "failure_class": None,
                    "metadata": {},
                    "traceback": "",
                },
                "blocked_by": [],
                "outcome_source": "fresh",
            },
            "decoder": {
                "node_id": "decoder",
                "status": "blocked",
                "output": None,
                "error": None,
                "blocked_by": ["encoder"],
                "outcome_source": "fresh",
            },
        },
        "execution_order": ["encoder", "decoder"],
        "terminal_node_id": "decoder",
        "terminal_output": None,
        "terminal_error": {
            "node_id": "decoder",
            "status": "blocked",
            "error": None,
            "blocked_by": ["encoder"],
        },
    }


def test_cancelled_outcome_json_dump_is_persistable_shape() -> None:
    graph = _graph(_node("direct"), terminal_node_id="direct")

    def run_node(
        node: NodeConfig,
        inputs: Mapping[str, Any],
    ) -> NodeOutput:
        raise KeyboardInterrupt

    with pytest.raises(GraphRunInterruptedError) as exc_info:
        execute_graph(graph=graph, inputs={}, run_node=run_node)

    result = exc_info.value.partial_result
    assert result.model_dump(mode="json") == {
        "graph_hash": graph_hash(graph),
        "external_inputs": {},
        "status": "cancelled",
        "outcomes": {
            "direct": {
                "node_id": "direct",
                "status": "cancelled",
                "output": None,
                "error": None,
                "blocked_by": [],
                "outcome_source": "fresh",
            }
        },
        "execution_order": ["direct"],
        "terminal_node_id": "direct",
        "terminal_output": None,
        "terminal_error": {
            "node_id": "direct",
            "status": "cancelled",
            "error": None,
            "blocked_by": [],
        },
    }


def _minimal_result_kwargs() -> dict[str, Any]:
    return {"graph_hash": "0" * 64}


def _successful_result_fields() -> dict[str, Any]:
    graph = _graph(
        _node("source"),
        _node("terminal", input_sources={"value": "source"}),
        terminal_node_id="terminal",
    )
    return execute_graph(
        graph=graph,
        inputs={},
        run_node=lambda node, inputs: _output(node.node_id),
    ).model_dump()


def _error_result_fields() -> dict[str, Any]:
    graph = _graph(_node("terminal"), terminal_node_id="terminal")
    return execute_graph(
        graph=graph,
        inputs={},
        run_node=lambda node, inputs: _raise(RuntimeError("failed")),
    ).model_dump()


def _blocked_result_fields() -> dict[str, Any]:
    graph = _graph(
        _node("source"),
        _node("terminal", input_sources={"value": "source"}),
        terminal_node_id="terminal",
    )
    return execute_graph(
        graph=graph,
        inputs={},
        run_node=lambda node, inputs: _raise(RuntimeError("failed")),
    ).model_dump()


def test_graph_run_result_requires_outcomes() -> None:
    fields = _successful_result_fields()
    fields["outcomes"] = {}
    fields["execution_order"] = ()

    with pytest.raises(ValueError, match="at least one outcome"):
        GraphRunResult(**fields)


def test_graph_run_result_requires_terminal_outcome() -> None:
    fields = _successful_result_fields()
    fields["outcomes"].pop("terminal")
    fields["execution_order"] = ("source",)

    with pytest.raises(ValueError, match=r"terminal_node_id.*outcomes"):
        GraphRunResult(**fields)


@pytest.mark.parametrize(
    "execution_order",
    [
        pytest.param(("source",), id="missing-node"),
        pytest.param(("source", "terminal", "other"), id="extra-node"),
        pytest.param(("source", "terminal", "terminal"), id="duplicate-node"),
    ],
)
def test_graph_run_result_requires_exact_execution_order(
    execution_order: tuple[str, ...],
) -> None:
    fields = _successful_result_fields()
    fields["execution_order"] = execution_order

    with pytest.raises(ValueError, match="execution_order"):
        GraphRunResult(**fields)


def test_successful_graph_run_requires_every_outcome_to_succeed() -> None:
    fields = _successful_result_fields()
    fields["outcomes"]["source"] = NodeOutcome.from_error(
        node_id="source",
        error=RuntimeError("failed"),
    )

    with pytest.raises(ValueError, match="successful graph runs require"):
        GraphRunResult(**fields)


@pytest.mark.parametrize(
    ("fields_factory", "terminal_outcome"),
    [
        pytest.param(
            _error_result_fields,
            NodeOutcome.success(
                node_id="terminal",
                output=_output("unexpected"),
            ),
            id="error-status-success-outcome",
        ),
        pytest.param(
            _blocked_result_fields,
            NodeOutcome.from_error(
                node_id="terminal",
                error=RuntimeError("failed directly"),
            ),
            id="blocked-status-error-outcome",
        ),
    ],
)
def test_graph_run_status_must_match_terminal_outcome(
    fields_factory: Callable[[], dict[str, Any]],
    terminal_outcome: NodeOutcome,
) -> None:
    fields = fields_factory()
    fields["outcomes"]["terminal"] = terminal_outcome

    with pytest.raises(ValueError, match="status must match terminal outcome"):
        GraphRunResult(**fields)


def test_terminal_error_must_match_terminal_outcome() -> None:
    fields = _error_result_fields()
    fields["terminal_error"] = TerminalError(
        node_id="terminal",
        status=NodeOutcomeStatus.ERROR,
        error=NodeError(error_type="different", message="different"),
    )

    with pytest.raises(ValueError, match="must match terminal outcome"):
        GraphRunResult(**fields)


def test_terminal_error_rejects_success_status() -> None:
    with pytest.raises(
        ValueError,
        match="must be error, blocked, or cancelled",
    ):
        TerminalError(
            node_id="direct",
            status=NodeOutcomeStatus.SUCCESS,
        )


def test_graph_run_result_rejects_mismatched_outcome_keys() -> None:
    outcome = NodeOutcome.success(
        node_id="direct",
        output=_output("ok"),
    )
    with pytest.raises(ValueError, match="does not match node_id"):
        GraphRunResult(
            **_minimal_result_kwargs(),
            status=GraphRunStatus.SUCCESS,
            outcomes={"other": outcome},
            execution_order=("direct",),
            terminal_node_id="direct",
            terminal_output="ok",
        )


def _node_error() -> NodeError:
    return NodeError(error_type="test", message="failed")


def _terminal_error(
    *,
    status: NodeOutcomeStatus,
    node_id: str = "direct",
) -> TerminalError:
    if status is NodeOutcomeStatus.ERROR:
        return TerminalError(
            node_id=node_id,
            status=status,
            error=_node_error(),
        )
    return TerminalError(
        node_id=node_id,
        status=status,
        blocked_by=("upstream",),
    )


@pytest.mark.parametrize(
    ("status", "kwargs", "match"),
    [
        (
            GraphRunStatus.SUCCESS,
            {
                "terminal_error": _terminal_error(
                    status=NodeOutcomeStatus.ERROR
                ),
            },
            "cannot include terminal_error",
        ),
        (
            GraphRunStatus.ERROR,
            {},
            "require terminal_error",
        ),
        (
            GraphRunStatus.BLOCKED,
            {},
            "require terminal_error",
        ),
        (
            GraphRunStatus.ERROR,
            {
                "terminal_output": "ok",
                "terminal_error": _terminal_error(
                    status=NodeOutcomeStatus.ERROR
                ),
            },
            "both terminal_output and terminal_error",
        ),
        (
            GraphRunStatus.ERROR,
            {
                "terminal_error": _terminal_error(
                    status=NodeOutcomeStatus.ERROR,
                    node_id="other",
                ),
            },
            "must match terminal_node_id",
        ),
        (
            GraphRunStatus.ERROR,
            {
                "terminal_error": _terminal_error(
                    status=NodeOutcomeStatus.BLOCKED
                ),
            },
            "must be error for error graph runs",
        ),
        (
            GraphRunStatus.BLOCKED,
            {
                "terminal_error": _terminal_error(
                    status=NodeOutcomeStatus.ERROR
                ),
            },
            "must be blocked for blocked graph runs",
        ),
        (
            GraphRunStatus.CANCELLED,
            {},
            "require terminal_error",
        ),
    ],
)
def test_graph_run_result_rejects_invalid_terminal_shape(
    status: GraphRunStatus,
    kwargs: dict[str, Any],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        GraphRunResult(
            **_minimal_result_kwargs(),
            status=status,
            outcomes={},
            execution_order=(),
            terminal_node_id="direct",
            **kwargs,
        )


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        pytest.param(kwargs, match, id=case_id)
        for case_id, kwargs, match in failure_state_cases()
    ],
)
def test_terminal_error_rejects_invalid_field_combinations(
    kwargs: dict[str, Any],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        TerminalError(**kwargs)
