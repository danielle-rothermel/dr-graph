from __future__ import annotations

import pytest

from dr_graph import (
    FieldRole,
    GraphDefinition,
    NodeDefinition,
    NodeFieldSpec,
    NodeInputSourceRef,
    graph,
    graph_hash,
    node,
)


def _encdec_definition() -> GraphDefinition:
    return GraphDefinition(
        schema_version=1,
        nodes=(
            NodeDefinition(
                node_id="encoder",
                node_type="llm_call",
                fields=(
                    NodeFieldSpec(name="prompt", role=FieldRole.INPUT),
                    NodeFieldSpec(name="description", role=FieldRole.OUTPUT),
                ),
                input_sources={
                    "prompt": NodeInputSourceRef.model_validate("task.prompt")
                },
                output_field="description",
                variable_names=frozenset({"user_prompt_template"}),
            ),
            NodeDefinition(
                node_id="decoder",
                node_type="llm_call",
                fields=(
                    NodeFieldSpec(name="description", role=FieldRole.INPUT),
                    NodeFieldSpec(name="code", role=FieldRole.OUTPUT),
                ),
                input_sources={
                    "description": NodeInputSourceRef.model_validate(
                        "encoder.description"
                    )
                },
                output_field="code",
                variable_names=frozenset({"user_prompt_template"}),
            ),
        ),
        terminal_node_id="decoder",
    )


def test_definition_materializes_multiple_distinct_configs() -> None:
    definition = _encdec_definition()

    config_a = definition.materialize(
        {
            "encoder": {"user_prompt_template": "Describe {prompt}"},
            "decoder": {
                "user_prompt_template": "Write code from {description}"
            },
        }
    )
    config_b = definition.materialize(
        {
            "encoder": {"user_prompt_template": "Summarize {prompt}"},
            "decoder": {"user_prompt_template": "Emit code for {description}"},
        }
    )

    assert config_a.terminal_node_id == "decoder"
    assert config_b.node_ids() == ["encoder", "decoder"]
    assert config_a.node("encoder").variables == {
        "user_prompt_template": "Describe {prompt}"
    }
    assert graph_hash(config_a) != graph_hash(config_b)


def test_materialized_config_hash_matches_direct_config() -> None:
    definition = _encdec_definition()

    materialized = definition.materialize(
        {
            "encoder": {"user_prompt_template": "Describe {prompt}"},
            "decoder": {
                "user_prompt_template": "Write code from {description}"
            },
        }
    )
    direct = graph(
        [
            node(
                "encoder",
                node_type="llm_call",
                fields=(
                    NodeFieldSpec(name="prompt", role=FieldRole.INPUT),
                    NodeFieldSpec(name="description", role=FieldRole.OUTPUT),
                ),
                input_sources={"prompt": "task.prompt"},
                output_field="description",
                variables={"user_prompt_template": "Describe {prompt}"},
            ),
            node(
                "decoder",
                node_type="llm_call",
                fields=(
                    NodeFieldSpec(name="description", role=FieldRole.INPUT),
                    NodeFieldSpec(name="code", role=FieldRole.OUTPUT),
                ),
                input_sources={"description": "encoder.description"},
                output_field="code",
                variables={
                    "user_prompt_template": "Write code from {description}"
                },
            ),
        ],
        terminal="decoder",
    )
    assert graph_hash(materialized) == graph_hash(direct)


def test_materialize_rejects_missing_required_variable() -> None:
    definition = _encdec_definition()
    with pytest.raises(ValueError, match="missing required variable"):
        definition.materialize(
            {
                "encoder": {},
                "decoder": {"user_prompt_template": "x"},
            }
        )


def test_materialize_rejects_undeclared_variable() -> None:
    definition = _encdec_definition()
    with pytest.raises(ValueError, match="sets undeclared variable"):
        definition.materialize(
            {
                "encoder": {
                    "user_prompt_template": "x",
                    "surprise": "y",
                },
                "decoder": {"user_prompt_template": "z"},
            }
        )


def test_materialize_rejects_unknown_node_id() -> None:
    definition = _encdec_definition()
    with pytest.raises(
        ValueError,
        match="reference unknown node id",
    ):
        definition.materialize(
            {
                "encoder": {"user_prompt_template": "x"},
                "decoder": {"user_prompt_template": "y"},
                "typo": {"user_prompt_template": "z"},
            }
        )
