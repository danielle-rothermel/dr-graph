from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dr_graph import (
    GraphRunStatus,
    InputResolutionError,
    NodeConfig,
    NodeOutcomeStatus,
    NodeOutput,
    execute_graph,
)
from tests.support import _graph, _node, _output


def test_two_node_graph_binds_upstream_output_into_downstream_input() -> None:
    encoder = _node(
        "encoder",
        input_sources={"prompt": "task.prompt"},
        output_field="description",
    )
    decoder = _node(
        "decoder",
        input_sources={"description": "encoder.description"},
        output_field="code",
    )
    graph = _graph(decoder, encoder, terminal_node_id="decoder")
    seen_inputs: dict[str, Mapping[str, Any]] = {}

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        seen_inputs[node.node_id] = dict(inputs)
        if node.node_id == "encoder":
            return _output("plain description", field="description")
        return _output(
            f"def f(): return {inputs['description']!r}",
            field="code",
        )

    result = execute_graph(
        graph=graph,
        inputs={"prompt": "write f"},
        run_node=run_node,
    )

    assert result.status is GraphRunStatus.SUCCESS
    assert result.execution_order == ("encoder", "decoder")
    assert seen_inputs["decoder"] == {"description": "plain description"}
    assert result.terminal_output == "def f(): return 'plain description'"


def test_missing_task_input_becomes_error_outcome() -> None:
    graph = _graph(
        _node("direct", input_sources={"prompt": "task.prompt"}),
        terminal_node_id="direct",
    )

    result = execute_graph(
        graph=graph,
        inputs={},
        run_node=lambda node, inputs: _output("unreachable"),
    )

    outcome = result.outcomes["direct"]
    assert result.status is GraphRunStatus.ERROR
    assert outcome.status is NodeOutcomeStatus.ERROR
    assert outcome.error is not None
    assert outcome.error.error_type == (
        f"{InputResolutionError.__module__}."
        f"{InputResolutionError.__qualname__}"
    )
    assert outcome.error.failure_class == "infrastructure"
    assert result.terminal_error is not None
    assert result.terminal_error.error == outcome.error


def test_all_declared_outputs_are_available_to_downstream_nodes() -> None:
    graph = _graph(
        _node(
            "producer",
            output_field="primary",
            output_fields=("primary", "secondary"),
        ),
        _node(
            "consumer",
            input_sources={"value": "producer.secondary"},
            output_field="result",
        ),
        terminal_node_id="consumer",
    )

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        if node.node_id == "producer":
            return NodeOutput(
                values={"primary": "default", "secondary": "named"}
            )
        return NodeOutput(values={"result": f"used {inputs['value']}"})

    result = execute_graph(graph=graph, inputs={}, run_node=run_node)

    assert result.status is GraphRunStatus.SUCCESS
    assert result.terminal_output == "used named"


def test_default_node_ref_uses_upstream_configured_output_field() -> None:
    graph = _graph(
        _node("encoder", output_field="description"),
        _node("decoder", input_sources={"description": "encoder"}),
        terminal_node_id="decoder",
    )

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        if node.node_id == "encoder":
            return _output("summary", field="description")
        return _output(inputs["description"])

    result = execute_graph(graph=graph, inputs={}, run_node=run_node)

    assert result.terminal_output == "summary"
