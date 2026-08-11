from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from dr_serialize import StrictJsonError

from dr_graph import (
    FieldRole,
    GraphRunInterruptedError,
    GraphRunStatus,
    NodeConfig,
    NodeFieldSpec,
    NodeOutcomeSource,
    NodeOutcomeStatus,
    NodeOutput,
    execute_graph,
    graph_hash,
)
from tests.support import PermanentFailureError, _graph, _node, _output


def test_direct_one_node_graph_success() -> None:
    graph = _graph(
        _node("direct", input_sources={"prompt": "task.prompt"}),
        terminal_node_id="direct",
    )

    result = execute_graph(
        graph=graph,
        inputs={"prompt": "write add"},
        run_node=lambda node, inputs: _output(f"code for {inputs['prompt']}"),
    )

    assert result.status is GraphRunStatus.SUCCESS
    assert result.execution_order == ("direct",)
    assert result.terminal_output == "code for write add"
    assert result.outcomes["direct"].status is NodeOutcomeStatus.SUCCESS
    assert result.graph_hash == graph_hash(graph)
    assert result.external_inputs == {"prompt": "write add"}


def test_topological_order_is_deterministic_for_independent_nodes() -> None:
    graph = _graph(
        _node("middle", input_sources={"z": "zeta", "a": "alpha"}),
        _node("zeta"),
        _node("alpha"),
        terminal_node_id="middle",
    )

    result = execute_graph(
        graph=graph,
        inputs={},
        run_node=lambda node, inputs: _output(node.node_id),
    )

    assert result.execution_order == ("alpha", "zeta", "middle")
    assert result.terminal_output == "middle"


def test_node_exception_captures_persistable_error() -> None:
    graph = _graph(_node("direct"), terminal_node_id="direct")
    error = PermanentFailureError(
        "provider rejected request",
        metadata={"provider": "test"},
    )

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        raise error

    result = execute_graph(graph=graph, inputs={}, run_node=run_node)

    outcome = result.outcomes["direct"]
    dumped = result.model_dump(mode="json")
    assert result.status is GraphRunStatus.ERROR
    assert outcome.status is NodeOutcomeStatus.ERROR
    assert outcome.error is not None
    assert outcome.error.failure_class == "permanent"
    assert outcome.error.metadata == {"provider": "test"}
    assert outcome.error.traceback
    assert "exception" not in dumped["outcomes"]["direct"]


def test_downstream_nodes_are_blocked_when_dependency_errors() -> None:
    graph = _graph(
        _node("encoder", input_sources={"prompt": "task.prompt"}),
        _node("decoder", input_sources={"description": "encoder"}),
        terminal_node_id="decoder",
    )
    invoked: list[str] = []

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        invoked.append(node.node_id)
        if node.node_id == "encoder":
            raise RuntimeError("encoder failed")
        return _output("unreachable")

    result = execute_graph(
        graph=graph,
        inputs={"prompt": "write f"},
        run_node=run_node,
    )

    assert invoked == ["encoder"]
    assert result.status is GraphRunStatus.BLOCKED
    assert result.outcomes["encoder"].status is NodeOutcomeStatus.ERROR
    assert result.outcomes["decoder"].status is NodeOutcomeStatus.BLOCKED
    assert result.outcomes["decoder"].blocked_by == ("encoder",)
    assert result.terminal_error is not None
    assert result.terminal_error.status is NodeOutcomeStatus.BLOCKED
    assert result.terminal_error.blocked_by == ("encoder",)


def test_blocked_node_lists_all_failed_dependencies() -> None:
    graph = _graph(
        _node("terminal", input_sources={"left": "a", "right": "b"}),
        _node("b"),
        _node("a"),
        terminal_node_id="terminal",
    )

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        if node.node_id in {"a", "b"}:
            raise RuntimeError(f"{node.node_id} errored")
        return _output("unreachable")

    result = execute_graph(graph=graph, inputs={}, run_node=run_node)

    assert result.status is GraphRunStatus.BLOCKED
    assert result.outcomes["terminal"].status is NodeOutcomeStatus.BLOCKED
    assert result.outcomes["terminal"].blocked_by == ("a", "b")


def test_unhashable_graph_raises_before_run_node_is_invoked() -> None:
    node = NodeConfig(
        node_id="direct",
        node_type="llm_call",
        fields=(NodeFieldSpec(name="output", role=FieldRole.OUTPUT),),
        output_field="output",
        variables={"x": float("nan")},
    )
    graph = _graph(node, terminal_node_id="direct")
    invoked: list[str] = []

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        invoked.append(node.node_id)
        return _output("unreachable")

    with pytest.raises(StrictJsonError):
        execute_graph(graph=graph, inputs={}, run_node=run_node)

    assert invoked == []


def test_invalid_external_inputs_raise_before_run_node_is_invoked() -> None:
    graph = _graph(_node("direct"), terminal_node_id="direct")
    invoked: list[str] = []

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        invoked.append(node.node_id)
        return _output("unreachable")

    with pytest.raises(StrictJsonError):
        execute_graph(
            graph=graph,
            inputs={"unused": object()},
            run_node=run_node,
        )

    assert invoked == []


def test_external_inputs_are_snapshotted_before_node_invocation() -> None:
    graph = _graph(
        _node("direct", input_sources={"payload": "task.payload"}),
        terminal_node_id="direct",
    )
    inputs = {"payload": {"items": []}}

    def run_node(
        node: NodeConfig,
        node_inputs: Mapping[str, Any],
    ) -> NodeOutput:
        payload = node_inputs["payload"]
        assert isinstance(payload, dict)
        items = payload["items"]
        assert isinstance(items, list)
        items.append("mutated")
        return _output("done")

    result = execute_graph(graph=graph, inputs=inputs, run_node=run_node)

    assert inputs == {"payload": {"items": ["mutated"]}}
    assert result.external_inputs == {"payload": {"items": []}}


def test_keyboard_interrupt_preserves_partial_graph_run_result() -> None:
    graph = _graph(
        _node(
            "encoder",
            input_sources={"prompt": "task.prompt"},
            output_field="description",
        ),
        _node("decoder", input_sources={"description": "encoder"}),
        terminal_node_id="decoder",
    )

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        if node.node_id == "encoder":
            return _output("prior description", field="description")
        raise KeyboardInterrupt

    with pytest.raises(GraphRunInterruptedError) as exc_info:
        execute_graph(
            graph=graph,
            inputs={"prompt": "write f"},
            run_node=run_node,
        )

    partial = exc_info.value.partial_result
    assert partial.status is GraphRunStatus.CANCELLED
    encoder = partial.outcomes["encoder"]
    decoder = partial.outcomes["decoder"]
    assert encoder.outcome_source is NodeOutcomeSource.FRESH
    assert decoder.status is NodeOutcomeStatus.CANCELLED
    assert decoder.outcome_source is NodeOutcomeSource.FRESH
    assert partial.execution_order == ("encoder", "decoder")
