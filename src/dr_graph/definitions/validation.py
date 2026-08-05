from __future__ import annotations

from typing import TYPE_CHECKING

from dr_graph.core.errors import GraphValidationError
from dr_graph.core.fields import validate_node_fields
from dr_graph.core.input_sources import validate_ref_identifier
from dr_graph.core.topology import (
    topological_order_ids,
    validate_single_terminal_ids,
)

if TYPE_CHECKING:
    from dr_graph.definitions.graphs import GraphDefinition
    from dr_graph.definitions.nodes import NodeDefinition


def validate_node_definition(definition: NodeDefinition) -> None:
    validate_ref_identifier(definition.node_id, kind="node id")
    validate_node_fields(
        definition.fields,
        definition.input_sources,
        definition.output_field,
    )


def validate_graph_definition(definition: GraphDefinition) -> None:
    if not definition.nodes:
        raise GraphValidationError(
            "graph definition must have at least one node"
        )
    node_ids = definition.node_ids()
    if len(node_ids) != len(set(node_ids)):
        raise GraphValidationError("duplicate node ids")
    known = set(node_ids)
    if definition.terminal_node_id not in known:
        raise GraphValidationError(
            f"terminal_node_id {definition.terminal_node_id!r} not in "
            "graph definition"
        )
    dependencies = {
        node.node_id: node.dependencies() for node in definition.nodes
    }
    for node_id, deps in dependencies.items():
        unknown = sorted(deps - known)
        if unknown:
            joined = ", ".join(repr(dep) for dep in unknown)
            raise GraphValidationError(
                f"node {node_id!r} depends on unknown node(s) {joined}"
            )
    topological_order_ids(node_ids, dependencies)
    validate_single_terminal_ids(
        node_ids,
        dependencies,
        terminal_node_id=definition.terminal_node_id,
    )
