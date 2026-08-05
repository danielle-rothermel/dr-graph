from __future__ import annotations

from typing import Any

import pytest

from dr_graph import (
    GraphRunResult,
    GraphRunStatus,
    NodeError,
    NodeOutcome,
    NodeOutcomeStatus,
    TerminalError,
    execute_graph,
    graph_hash,
)
from tests.core.support import _graph, _node, _output


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
            }
        },
        "execution_order": ["direct"],
        "terminal_node_id": "direct",
        "terminal_output": "ok",
        "terminal_error": None,
        "attempt_evidence_refs": [],
        "provenance": {},
    }


def test_error_outcome_json_dump_is_persistable_shape() -> None:
    graph = _graph(_node("direct"), terminal_node_id="direct")

    result = execute_graph(
        graph=graph,
        inputs={},
        run_node=lambda node, inputs: (_ for _ in ()).throw(
            RuntimeError("boom")
        ),
    )

    outcome = result.outcomes["direct"]
    assert outcome.error is not None
    assert result.model_dump(mode="json") == {
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
                },
                "blocked_by": [],
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
            },
            "blocked_by": [],
        },
        "attempt_evidence_refs": [],
        "provenance": {},
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
        run_node=lambda node, inputs: (_ for _ in ()).throw(
            RuntimeError("encoder failed")
        ),
    )

    assert result.model_dump(mode="json") == {
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
                },
                "blocked_by": [],
            },
            "decoder": {
                "node_id": "decoder",
                "status": "blocked",
                "output": None,
                "error": None,
                "blocked_by": ["encoder"],
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
        "attempt_evidence_refs": [],
        "provenance": {},
    }


def _minimal_result_kwargs() -> dict[str, Any]:
    return {"graph_hash": "0" * 64}


def test_terminal_error_rejects_success_status() -> None:
    with pytest.raises(ValueError, match="must be error or blocked"):
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


def test_graph_run_result_rejects_conflicting_terminal_fields() -> None:
    with pytest.raises(
        ValueError,
        match="both terminal_output and terminal_error",
    ):
        GraphRunResult(
            **_minimal_result_kwargs(),
            status=GraphRunStatus.ERROR,
            outcomes={},
            execution_order=(),
            terminal_node_id="direct",
            terminal_output="ok",
            terminal_error=TerminalError(
                node_id="direct",
                status=NodeOutcomeStatus.ERROR,
                error=NodeError(error_type="test", message="failed"),
            ),
        )


def _node_error() -> NodeError:
    return NodeError(error_type="test", message="failed")


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        (
            {"node_id": "n", "status": NodeOutcomeStatus.SUCCESS},
            "require output",
        ),
        (
            {
                "node_id": "n",
                "status": NodeOutcomeStatus.SUCCESS,
                "output": _output("ok"),
                "error": _node_error(),
            },
            "cannot include error",
        ),
        (
            {
                "node_id": "n",
                "status": NodeOutcomeStatus.SUCCESS,
                "output": _output("ok"),
                "blocked_by": ("upstream",),
            },
            "cannot include blocked_by",
        ),
        (
            {"node_id": "n", "status": NodeOutcomeStatus.ERROR},
            "require error",
        ),
        (
            {
                "node_id": "n",
                "status": NodeOutcomeStatus.ERROR,
                "error": _node_error(),
                "output": _output("ok"),
            },
            "cannot include output",
        ),
        (
            {
                "node_id": "n",
                "status": NodeOutcomeStatus.ERROR,
                "error": _node_error(),
                "blocked_by": ("upstream",),
            },
            "cannot include blocked_by",
        ),
        (
            {"node_id": "n", "status": NodeOutcomeStatus.BLOCKED},
            "require blocked_by",
        ),
        (
            {
                "node_id": "n",
                "status": NodeOutcomeStatus.BLOCKED,
                "blocked_by": ("upstream",),
                "output": _output("ok"),
            },
            "cannot include output",
        ),
        (
            {
                "node_id": "n",
                "status": NodeOutcomeStatus.BLOCKED,
                "blocked_by": ("upstream",),
                "error": _node_error(),
            },
            "cannot include error",
        ),
    ],
)
def test_node_outcome_rejects_invalid_field_combinations(
    kwargs: dict[str, Any],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        NodeOutcome(**kwargs)


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
        (
            {"node_id": "n", "status": NodeOutcomeStatus.ERROR},
            "require error",
        ),
        (
            {
                "node_id": "n",
                "status": NodeOutcomeStatus.ERROR,
                "error": _node_error(),
                "blocked_by": ("upstream",),
            },
            "cannot include blocked_by",
        ),
        (
            {"node_id": "n", "status": NodeOutcomeStatus.BLOCKED},
            "require blocked_by",
        ),
        (
            {
                "node_id": "n",
                "status": NodeOutcomeStatus.BLOCKED,
                "blocked_by": ("upstream",),
                "error": _node_error(),
            },
            "cannot include error",
        ),
    ],
)
def test_terminal_error_rejects_invalid_field_combinations(
    kwargs: dict[str, Any],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        TerminalError(**kwargs)
