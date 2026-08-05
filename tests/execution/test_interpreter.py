from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from dr_serialize import StrictJsonError

from dr_graph import (
    FieldRole,
    GraphRunStatus,
    InputResolutionError,
    NodeConfig,
    NodeExecutionError,
    NodeFieldSpec,
    NodeOutcomeStatus,
    NodeOutput,
    execute_graph,
    graph_hash,
)
from tests.core.support import PermanentFailureError, _graph, _node, _output


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
    graph = _graph(
        decoder,
        encoder,
        terminal_node_id="decoder",
    )
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
    assert result.terminal_error is not None
    assert result.terminal_error.error == outcome.error


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
    assert "exception" not in dumped["outcomes"]["direct"]


def test_invalid_exception_metadata_does_not_escape_execution() -> None:
    class InvalidMetadataError(Exception):
        def __init__(self) -> None:
            super().__init__("callback failed")
            self.metadata = {"opaque": object()}

    graph = _graph(_node("direct"), terminal_node_id="direct")

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        raise InvalidMetadataError

    result = execute_graph(graph=graph, inputs={}, run_node=run_node)

    outcome = result.outcomes["direct"]
    assert result.status is GraphRunStatus.ERROR
    assert outcome.error is not None
    assert outcome.error.metadata == {}


def test_node_error_preserves_wrapped_step_failure_diagnostics() -> None:
    class StepFailure(Exception):  # noqa: N818 -- mirrors a wrapped step failure
        def __init__(self) -> None:
            super().__init__("provider failed")
            self.error_type = "builtins.RuntimeError"
            self.failure_class = "permanent"
            self.metadata = {"provider": "test"}

    graph = _graph(_node("direct"), terminal_node_id="direct")

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        raise StepFailure

    result = execute_graph(graph=graph, inputs={}, run_node=run_node)

    outcome = result.outcomes["direct"]
    assert outcome.error is not None
    assert outcome.error.error_type == "builtins.RuntimeError"
    assert outcome.error.failure_class == "permanent"
    assert outcome.error.metadata == {"provider": "test"}
    assert result.terminal_error is not None
    assert result.terminal_error.error == outcome.error


def test_node_error_preserves_underlying_exception_type() -> None:
    graph = _graph(_node("direct"), terminal_node_id="direct")
    error = PermanentFailureError(
        "classified failure",
        underlying=ValueError("bad payload"),
        metadata={"stage": "parse"},
    )

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        raise error

    result = execute_graph(graph=graph, inputs={}, run_node=run_node)

    outcome = result.outcomes["direct"]
    assert outcome.error is not None
    assert outcome.error.metadata == {
        "stage": "parse",
        "underlying_exception_type": "builtins.ValueError",
    }


def test_node_error_preserves_chained_underlying_exception_type() -> None:
    graph = _graph(_node("direct"), terminal_node_id="direct")
    error = PermanentFailureError(
        "outer",
        underlying=PermanentFailureError(
            "middle",
            underlying=ValueError("inner"),
        ),
        metadata={"stage": "parse"},
    )

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        raise error

    result = execute_graph(graph=graph, inputs={}, run_node=run_node)

    outcome = result.outcomes["direct"]
    assert outcome.error is not None
    assert outcome.error.metadata["underlying_exception_type"] == (
        "builtins.ValueError"
    )


def test_downstream_nodes_are_blocked_when_dependency_errors() -> None:
    graph = _graph(
        _node("encoder", input_sources={"prompt": "task.prompt"}),
        _node("decoder", input_sources={"description": "encoder"}),
        terminal_node_id="decoder",
    )

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        if node.node_id == "encoder":
            raise RuntimeError("encoder failed")
        return _output("unreachable")

    result = execute_graph(
        graph=graph,
        inputs={"prompt": "write f"},
        run_node=run_node,
    )

    assert result.status is GraphRunStatus.BLOCKED
    assert result.outcomes["encoder"].status is NodeOutcomeStatus.ERROR
    assert result.outcomes["decoder"].status is NodeOutcomeStatus.BLOCKED
    assert result.outcomes["decoder"].blocked_by == ("encoder",)
    assert result.terminal_error is not None
    assert result.terminal_error.status is NodeOutcomeStatus.BLOCKED
    assert result.terminal_error.blocked_by == ("encoder",)


def test_blocked_nodes_do_not_invoke_run_node() -> None:
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
    assert result.outcomes["decoder"].status is NodeOutcomeStatus.BLOCKED


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


def test_unhashable_graph_raises_before_run_node_is_invoked() -> None:
    # graph_hash must be computed up front: a non-finite float Variable makes
    # the config unhashable, and that failure must precede any run_node
    # side effect rather than surfacing only inside _build_result.
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
