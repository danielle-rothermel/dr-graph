from __future__ import annotations

from dr_graph import (
    GraphRunStatus,
    NodeExecutionError,
    NodeOutcomeStatus,
    NodeOutput,
    execute_graph,
)
from tests.support import _graph, _node, _output


def test_run_node_dict_return_is_coerced_to_node_output() -> None:
    graph = _graph(_node("direct"), terminal_node_id="direct")

    result = execute_graph(
        graph=graph,
        inputs={},
        run_node=lambda node, inputs: {
            "values": {"output": "ok"},
            "metadata": {},
        },
    )

    assert result.status is GraphRunStatus.SUCCESS
    assert result.terminal_output == "ok"


def test_missing_returned_output_field_becomes_node_execution_error() -> None:
    graph = _graph(
        _node("direct", output_field="code"),
        terminal_node_id="direct",
    )

    result = execute_graph(
        graph=graph,
        inputs={},
        run_node=lambda node, inputs: _output("wrong", field="text"),
    )

    outcome = result.outcomes["direct"]
    assert result.status is GraphRunStatus.ERROR
    assert outcome.status is NodeOutcomeStatus.ERROR
    assert outcome.error is not None
    assert outcome.error.error_type == (
        f"{NodeExecutionError.__module__}.{NodeExecutionError.__qualname__}"
    )


def test_missing_secondary_output_becomes_producer_execution_error() -> None:
    graph = _graph(
        _node(
            "producer",
            output_field="primary",
            output_fields=("primary", "secondary"),
        ),
        terminal_node_id="producer",
    )

    result = execute_graph(
        graph=graph,
        inputs={},
        run_node=lambda node, inputs: NodeOutput(
            values={"primary": "present"}
        ),
    )

    outcome = result.outcomes["producer"]
    assert result.status is GraphRunStatus.ERROR
    assert outcome.status is NodeOutcomeStatus.ERROR
    assert outcome.error is not None
    assert outcome.error.error_type == (
        f"{NodeExecutionError.__module__}.{NodeExecutionError.__qualname__}"
    )
    assert "secondary" in outcome.error.message


def test_invalid_run_node_return_shape_becomes_error_outcome() -> None:
    graph = _graph(_node("direct"), terminal_node_id="direct")

    result = execute_graph(
        graph=graph,
        inputs={},
        run_node=lambda node, inputs: {"values": "not a dict"},
    )

    outcome = result.outcomes["direct"]
    assert result.status is GraphRunStatus.ERROR
    assert outcome.status is NodeOutcomeStatus.ERROR
    assert outcome.error is not None
    assert "ValidationError" in outcome.error.error_type
