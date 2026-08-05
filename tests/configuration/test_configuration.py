from __future__ import annotations

import pytest

from dr_graph import (
    FieldRole,
    GraphConfig,
    NodeConfig,
    NodeFieldSpec,
    NodeInputSourceRef,
    validate_graph_external_inputs,
)
from tests.core.support import _graph, _node


def test_duplicate_node_id_validation() -> None:
    with pytest.raises(ValueError, match="duplicate node ids"):
        GraphConfig(
            nodes=(_node("same"), _node("same")),
            terminal_node_id="same",
        )


def test_unknown_dependency_validation() -> None:
    with pytest.raises(ValueError, match="points at unknown node"):
        GraphConfig(
            nodes=(
                _node("decoder", input_sources={"description": "encoder"}),
            ),
            terminal_node_id="decoder",
        )


def test_cycle_detection() -> None:
    with pytest.raises(ValueError, match="graph has a cycle"):
        GraphConfig(
            nodes=(
                _node("a", input_sources={"value": "b"}),
                _node("b", input_sources={"value": "a"}),
            ),
            terminal_node_id="a",
        )


def test_empty_graph_validation() -> None:
    with pytest.raises(ValueError, match="graph must have at least one node"):
        GraphConfig(nodes=(), terminal_node_id="missing")


def test_missing_terminal_node_validation() -> None:
    with pytest.raises(
        ValueError,
        match="terminal_node_id 'missing' not in graph",
    ):
        GraphConfig(nodes=(_node("direct"),), terminal_node_id="missing")


def test_second_sink_node_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="more than one terminal/sink node",
    ):
        GraphConfig(
            nodes=(_node("terminal"), _node("bad")),
            terminal_node_id="terminal",
        )


def test_terminal_consumed_by_other_node_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="is consumed by another node and cannot be the sink",
    ):
        GraphConfig(
            nodes=(
                _node("encoder", output_field="description"),
                _node("decoder", input_sources={"description": "encoder"}),
            ),
            terminal_node_id="encoder",
        )


def test_node_config_requires_declared_fields() -> None:
    with pytest.raises(
        ValueError,
        match="node config must declare at least one field",
    ):
        NodeConfig(
            node_id="n",
            node_type="llm_call",
            fields=(),
            output_field="output",
        )


def test_node_config_rejects_duplicate_field_names() -> None:
    with pytest.raises(ValueError, match="duplicate field names"):
        NodeConfig(
            node_id="n",
            node_type="llm_call",
            fields=(
                NodeFieldSpec(name="output", role=FieldRole.OUTPUT),
                NodeFieldSpec(name="output", role=FieldRole.OUTPUT),
            ),
            output_field="output",
        )


def test_node_config_rejects_unknown_output_field() -> None:
    with pytest.raises(
        ValueError,
        match="output_field 'missing' is not an output field",
    ):
        NodeConfig(
            node_id="n",
            node_type="llm_call",
            fields=(NodeFieldSpec(name="output", role=FieldRole.OUTPUT),),
            output_field="missing",
        )


def test_node_config_rejects_source_to_undeclared_input_field() -> None:
    with pytest.raises(
        ValueError,
        match="input source 'prompt' is not an input field",
    ):
        NodeConfig(
            node_id="n",
            node_type="llm_call",
            fields=(NodeFieldSpec(name="output", role=FieldRole.OUTPUT),),
            input_sources={
                "prompt": NodeInputSourceRef.model_validate("task.prompt")
            },
            output_field="output",
        )


def test_node_config_rejects_input_field_without_source() -> None:
    with pytest.raises(
        ValueError,
        match="input field\\(s\\) 'prompt' have no input source",
    ):
        NodeConfig(
            node_id="n",
            node_type="llm_call",
            fields=(
                NodeFieldSpec(name="prompt", role=FieldRole.INPUT),
                NodeFieldSpec(name="output", role=FieldRole.OUTPUT),
            ),
            output_field="output",
        )


def test_unknown_task_input_field_validation() -> None:
    graph = _graph(
        _node("direct", input_sources={"prompt": "task.promt"}),
        terminal_node_id="direct",
    )
    with pytest.raises(
        ValueError,
        match=(
            "graph external input\\(s\\) 'promt' not in allowed "
            "external fields"
        ),
    ):
        validate_graph_external_inputs(graph, allowed_fields=("prompt",))


def test_graph_with_task_sources_does_not_require_task_fields() -> None:
    graph = _graph(
        _node("direct", input_sources={"prompt": "task.prompt"}),
        terminal_node_id="direct",
    )
    assert graph.model_dump(mode="json")["nodes"]
    validate_graph_external_inputs(graph, allowed_fields=("prompt",))


def test_missing_named_upstream_output_field_validation() -> None:
    with pytest.raises(ValueError, match="points at unknown field 'other'"):
        GraphConfig(
            nodes=(
                _node("encoder", output_field="description"),
                _node(
                    "decoder",
                    input_sources={"description": "encoder.other"},
                ),
            ),
            terminal_node_id="decoder",
        )


def test_input_source_round_trips_through_graph_config_json_dump() -> None:
    graph = _graph(
        _node(
            "encoder",
            input_sources={"prompt": "task.prompt"},
            output_field="description",
        ),
        _node(
            "decoder",
            input_sources={"description": "encoder.description"},
            output_field="code",
        ),
        terminal_node_id="decoder",
    )

    payload = graph.model_dump(mode="json")
    assert payload["nodes"][0]["input_sources"]["prompt"] == "task.prompt"
    assert payload["nodes"][1]["input_sources"]["description"] == (
        "encoder.description"
    )

    round_tripped = GraphConfig.model_validate(payload)
    assert round_tripped == graph


def test_node_id_rejects_ref_grammar_tokens() -> None:
    with pytest.raises(ValueError, match=r"cannot contain '\.'"):
        _node("a.b")
    with pytest.raises(ValueError, match=r"'task' is reserved"):
        _node("task")
