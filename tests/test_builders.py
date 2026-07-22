from __future__ import annotations

import pytest

from dr_graph import (
    FieldRole,
    GraphRunStatus,
    NodeFieldSpec,
    NodeInputSourceRef,
    execute_graph,
    graph,
    graph_hash,
    node,
)


def test_node_derives_fields_from_input_sources_and_output() -> None:
    node_config = node(
        "encoder",
        node_type="llm_call",
        input_sources={"prompt": "task.prompt"},
        output_field="description",
        variables={"user_prompt_template": "{prompt}"},
    )
    assert node_config.node_type == "llm_call"
    assert [f.name for f in node_config.input_fields()] == ["prompt"]
    assert [f.name for f in node_config.output_fields()] == ["description"]
    assert node_config.input_sources["prompt"].ref == "task.prompt"
    assert node_config.variables == {"user_prompt_template": "{prompt}"}


def test_node_accepts_open_node_type_strings() -> None:
    node_config = node("tool", node_type="tool_call", output_field="output")
    assert node_config.node_type == "tool_call"


def test_node_rejects_empty_node_type() -> None:
    with pytest.raises(ValueError, match="node_type"):
        node("tool", node_type="", output_field="output")


def test_node_accepts_explicit_fields() -> None:
    node_config = node(
        "scorer",
        node_type="score",
        input_sources={"code": "decoder.code"},
        output_field="score",
        fields=(
            NodeFieldSpec(name="code", role=FieldRole.INPUT, type_name="code"),
            NodeFieldSpec(
                name="score", role=FieldRole.OUTPUT, type_name="float"
            ),
        ),
    )
    assert node_config.fields[0].type_name == "code"
    assert node_config.fields[1].type_name == "float"


def test_node_accepts_prebuilt_input_source_refs() -> None:
    ref = NodeInputSourceRef.model_validate("encoder.description")
    node_config = node(
        "decoder",
        node_type="llm_call",
        input_sources={"description": ref},
        output_field="code",
    )
    assert node_config.input_sources["description"] is ref


def test_graph_builder_matches_manual_config_hash() -> None:
    built = graph(
        [
            node(
                "encoder",
                node_type="llm_call",
                input_sources={"prompt": "task.prompt"},
                output_field="description",
            ),
            node(
                "decoder",
                node_type="llm_call",
                input_sources={"description": "encoder.description"},
                output_field="code",
            ),
        ],
        terminal="decoder",
    )
    payload = built.model_dump(mode="json")
    from dr_graph import GraphConfig

    manual = GraphConfig.model_validate(payload)
    assert graph_hash(built) == graph_hash(manual)
    assert built.terminal_node_id == "decoder"


def test_built_graph_executes() -> None:
    config = graph(
        [
            node(
                "direct",
                node_type="llm_call",
                input_sources={"prompt": "task.prompt"},
                output_field="output",
            ),
        ],
        terminal="direct",
    )
    result = execute_graph(
        graph=config,
        inputs={"prompt": "hi"},
        run_node=lambda _node, inputs: {
            "values": {"output": inputs["prompt"].upper()}
        },
    )
    assert result.status is GraphRunStatus.SUCCESS
    assert result.terminal_output == "HI"


def test_graph_builder_validates_terminal() -> None:
    with pytest.raises(ValueError, match="not in graph"):
        graph(
            [node("a", node_type="llm_call", output_field="output")],
            terminal="missing",
        )
