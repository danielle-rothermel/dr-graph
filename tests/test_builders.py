from __future__ import annotations

import pytest

from dr_graph import (
    BindingRef,
    FieldRole,
    FieldSpec,
    GraphRunStatus,
    execute_graph,
    graph,
    graph_digest,
    node,
)


def test_node_derives_fields_from_bindings_and_output() -> None:
    spec = node(
        "encoder",
        op="llm_call",
        bindings={"prompt": "task.prompt"},
        output_field="description",
        metadata={"user_prompt_template": "{prompt}"},
    )
    assert spec.op == "llm_call"
    assert [f.name for f in spec.config.input_fields()] == ["prompt"]
    assert [f.name for f in spec.config.output_fields()] == ["description"]
    assert spec.config.input_bindings["prompt"].ref == "task.prompt"
    assert spec.config.metadata == {"user_prompt_template": "{prompt}"}


def test_node_accepts_open_op_strings() -> None:
    spec = node("tool", op="tool_call", output_field="output")
    assert spec.op == "tool_call"


def test_node_rejects_empty_op() -> None:
    with pytest.raises(ValueError, match="op"):
        node("tool", op="", output_field="output")


def test_node_accepts_explicit_fields() -> None:
    spec = node(
        "scorer",
        op="score",
        bindings={"code": "decoder.code"},
        output_field="score",
        fields=(
            FieldSpec(name="code", role=FieldRole.INPUT, type_name="code"),
            FieldSpec(name="score", role=FieldRole.OUTPUT, type_name="float"),
        ),
    )
    assert spec.config.fields[0].type_name == "code"
    assert spec.config.fields[1].type_name == "float"


def test_node_accepts_prebuilt_binding_refs() -> None:
    ref = BindingRef.model_validate("encoder.description")
    spec = node(
        "decoder",
        op="llm_call",
        bindings={"description": ref},
        output_field="code",
    )
    assert spec.config.input_bindings["description"] is ref


def test_graph_builder_matches_manual_spec_digest() -> None:
    built = graph(
        [
            node(
                "encoder",
                op="llm_call",
                bindings={"prompt": "task.prompt"},
                output_field="description",
            ),
            node(
                "decoder",
                op="llm_call",
                bindings={"description": "encoder.description"},
                output_field="code",
            ),
        ],
        terminal="decoder",
    )
    payload = built.model_dump(mode="json")
    from dr_graph import GraphSpec

    manual = GraphSpec.model_validate(payload)
    assert graph_digest(built) == graph_digest(manual)
    assert built.terminal_node_id == "decoder"


def test_built_graph_executes() -> None:
    spec = graph(
        [
            node(
                "direct",
                op="llm_call",
                bindings={"prompt": "task.prompt"},
                output_field="output",
            ),
        ],
        terminal="direct",
    )
    result = execute_graph(
        graph=spec,
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
            [node("a", op="llm_call", output_field="output")],
            terminal="missing",
        )
