from __future__ import annotations

import pytest

from dr_graph import (
    BindingRef,
    FieldRole,
    FieldSpec,
    GraphSpec,
    NodeConfig,
    validate_external_bindings,
)
from tests.support import _graph, _node


def test_duplicate_node_id_validation() -> None:
    with pytest.raises(ValueError, match="duplicate node ids"):
        GraphSpec(
            nodes=(_node("same"), _node("same")),
            terminal_node_id="same",
        )


def test_unknown_dependency_validation() -> None:
    with pytest.raises(ValueError, match="points at unknown node"):
        GraphSpec(
            nodes=(_node("decoder", bindings={"description": "encoder"}),),
            terminal_node_id="decoder",
        )


def test_cycle_detection() -> None:
    with pytest.raises(ValueError, match="graph has a cycle"):
        GraphSpec(
            nodes=(
                _node("a", bindings={"value": "b"}),
                _node("b", bindings={"value": "a"}),
            ),
            terminal_node_id="a",
        )


def test_empty_graph_validation() -> None:
    with pytest.raises(ValueError, match="graph must have at least one node"):
        GraphSpec(nodes=(), terminal_node_id="missing")


def test_missing_terminal_node_validation() -> None:
    with pytest.raises(
        ValueError,
        match="terminal_node_id 'missing' not in graph",
    ):
        GraphSpec(nodes=(_node("direct"),), terminal_node_id="missing")


def test_node_config_requires_declared_fields() -> None:
    with pytest.raises(
        ValueError,
        match="node config must declare at least one field",
    ):
        NodeConfig(fields=(), output_field="output")


def test_node_config_rejects_duplicate_field_names() -> None:
    with pytest.raises(ValueError, match="duplicate field names"):
        NodeConfig(
            fields=(
                FieldSpec(name="output", role=FieldRole.OUTPUT),
                FieldSpec(name="output", role=FieldRole.OUTPUT),
            ),
            output_field="output",
        )


def test_node_config_rejects_unknown_output_field() -> None:
    with pytest.raises(
        ValueError,
        match="output_field 'missing' is not an output field",
    ):
        NodeConfig(
            fields=(FieldSpec(name="output", role=FieldRole.OUTPUT),),
            output_field="missing",
        )


def test_node_config_rejects_binding_to_undeclared_input_field() -> None:
    with pytest.raises(
        ValueError,
        match="input binding 'prompt' is not an input field",
    ):
        NodeConfig(
            fields=(FieldSpec(name="output", role=FieldRole.OUTPUT),),
            input_bindings={
                "prompt": BindingRef.model_validate("task.prompt")
            },
            output_field="output",
        )


def test_unknown_task_binding_field_validation() -> None:
    graph = _graph(
        _node("direct", bindings={"prompt": "task.promt"}),
        terminal_node_id="direct",
    )
    with pytest.raises(
        ValueError,
        match=(
            "external binding field\\(s\\) 'promt' not in allowed "
            "external fields"
        ),
    ):
        validate_external_bindings(graph, allowed_fields=("prompt",))


def test_graph_with_task_bindings_does_not_require_task_fields() -> None:
    graph = _graph(
        _node("direct", bindings={"prompt": "task.prompt"}),
        terminal_node_id="direct",
    )
    assert graph.model_dump(mode="json")["nodes"]
    validate_external_bindings(graph, allowed_fields=("prompt",))


def test_missing_named_upstream_output_field_validation() -> None:
    with pytest.raises(ValueError, match="points at unknown field 'other'"):
        GraphSpec(
            nodes=(
                _node("encoder", output_field="description"),
                _node("decoder", bindings={"description": "encoder.other"}),
            ),
            terminal_node_id="decoder",
        )


def test_binding_ref_round_trips_through_graph_spec_json_dump() -> None:
    graph = _graph(
        _node(
            "encoder",
            bindings={"prompt": "task.prompt"},
            output_field="description",
        ),
        _node(
            "decoder",
            bindings={"description": "encoder.description"},
            output_field="code",
        ),
        terminal_node_id="decoder",
    )

    payload = graph.model_dump(mode="json")
    assert payload["nodes"][0]["config"]["input_bindings"]["prompt"] == (
        "task.prompt"
    )
    assert payload["nodes"][1]["config"]["input_bindings"]["description"] == (
        "encoder.description"
    )

    round_tripped = GraphSpec.model_validate(payload)
    assert round_tripped == graph


def test_node_id_rejects_ref_grammar_tokens() -> None:
    with pytest.raises(ValueError, match=r"cannot contain '\.'"):
        _node("a.b")
    with pytest.raises(ValueError, match=r"'task' is reserved"):
        _node("task")
