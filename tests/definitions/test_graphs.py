from __future__ import annotations

import pytest

from dr_graph import (
    FieldRole,
    GraphDefinition,
    NodeDefinition,
    NodeFieldSpec,
    NodeInputSourceRef,
)


def _topology_node(
    node_id: str,
    *,
    dependency: str | None = None,
) -> NodeDefinition:
    fields = [NodeFieldSpec(name="out", role=FieldRole.OUTPUT)]
    input_sources: dict[str, NodeInputSourceRef] = {}
    if dependency is not None:
        fields.insert(0, NodeFieldSpec(name="value", role=FieldRole.INPUT))
        input_sources["value"] = NodeInputSourceRef.model_validate(
            f"{dependency}.out"
        )
    return NodeDefinition(
        node_id=node_id,
        node_type="llm_call",
        fields=tuple(fields),
        input_sources=input_sources,
        output_field="out",
    )


def test_definition_enforces_single_terminal() -> None:
    with pytest.raises(ValueError, match="more than one terminal/sink node"):
        GraphDefinition(
            nodes=(
                _topology_node("a"),
                _topology_node("b"),
            ),
            terminal_node_id="a",
        )


@pytest.mark.parametrize(
    ("nodes", "terminal_node_id", "error_match"),
    [
        pytest.param(
            (),
            "missing",
            "graph definition must have at least one node",
            id="empty-nodes",
        ),
        pytest.param(
            (_topology_node("same"), _topology_node("same")),
            "same",
            "duplicate node ids",
            id="duplicate-node-ids",
        ),
        pytest.param(
            (_topology_node("direct"),),
            "missing",
            "terminal_node_id 'missing' not in graph definition",
            id="missing-terminal",
        ),
        pytest.param(
            (
                _topology_node("a", dependency="b"),
                _topology_node("b", dependency="a"),
            ),
            "a",
            "graph has a cycle among: a, b",
            id="cycle",
        ),
        pytest.param(
            (
                _topology_node("encoder"),
                _topology_node("decoder", dependency="encoder"),
            ),
            "encoder",
            "terminal node 'encoder' is consumed by another node",
            id="consumed-terminal",
        ),
    ],
)
def test_definition_rejects_invalid_graph_invariant(
    nodes: tuple[NodeDefinition, ...],
    terminal_node_id: str,
    error_match: str,
) -> None:
    with pytest.raises(ValueError, match=error_match):
        GraphDefinition(nodes=nodes, terminal_node_id=terminal_node_id)


def test_definition_rejects_unknown_dependency() -> None:
    with pytest.raises(ValueError, match="depends on unknown node"):
        GraphDefinition(
            nodes=(
                NodeDefinition(
                    node_id="a",
                    node_type="llm_call",
                    fields=(
                        NodeFieldSpec(name="seed", role=FieldRole.INPUT),
                        NodeFieldSpec(name="out", role=FieldRole.OUTPUT),
                    ),
                    input_sources={
                        "seed": NodeInputSourceRef.model_validate("missing")
                    },
                    output_field="out",
                ),
            ),
            terminal_node_id="a",
        )


def test_definition_rejects_unknown_named_output() -> None:
    with pytest.raises(ValueError, match="points at unknown field 'missing'"):
        GraphDefinition(
            nodes=(
                NodeDefinition(
                    node_id="producer",
                    node_type="llm_call",
                    fields=(
                        NodeFieldSpec(
                            name="actual",
                            role=FieldRole.OUTPUT,
                        ),
                    ),
                    output_field="actual",
                ),
                NodeDefinition(
                    node_id="consumer",
                    node_type="llm_call",
                    fields=(
                        NodeFieldSpec(name="value", role=FieldRole.INPUT),
                        NodeFieldSpec(name="result", role=FieldRole.OUTPUT),
                    ),
                    input_sources={
                        "value": NodeInputSourceRef.model_validate(
                            "producer.missing"
                        )
                    },
                    output_field="result",
                ),
            ),
            terminal_node_id="consumer",
        )
