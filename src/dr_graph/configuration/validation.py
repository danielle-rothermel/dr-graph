from __future__ import annotations

from typing import TYPE_CHECKING

from dr_graph.core.errors import GraphValidationError
from dr_graph.core.input_sources import validate_node_output_ref
from dr_graph.core.topology import (
    topological_order_ids,
    validate_single_terminal_ids,
)

if TYPE_CHECKING:
    from dr_graph.configuration.graphs import GraphConfig
    from dr_graph.configuration.nodes import NodeConfig


def validate_graph_config(graph: GraphConfig) -> None:
    if not graph.nodes:
        raise GraphValidationError("graph must have at least one node")
    node_ids = graph.node_ids()
    if len(node_ids) != len(set(node_ids)):
        raise GraphValidationError("duplicate node ids")
    nodes_by_id = {node.node_id: node for node in graph.nodes}
    if graph.terminal_node_id not in nodes_by_id:
        raise GraphValidationError(
            f"terminal_node_id {graph.terminal_node_id!r} not in graph"
        )
    output_names_by_node = {
        node_id: {field.name for field in source_node.output_fields()}
        for node_id, source_node in nodes_by_id.items()
    }
    for node in graph.nodes:
        for ref in node.input_sources.values():
            validate_node_output_ref(ref, output_names_by_node)
    dependencies = _dependencies_by_id(graph.nodes)
    topological_order_ids(node_ids, dependencies)
    validate_single_terminal_ids(
        node_ids,
        dependencies,
        terminal_node_id=graph.terminal_node_id,
    )


def _dependencies_by_id(
    nodes: tuple[NodeConfig, ...],
) -> dict[str, set[str]]:
    return {node.node_id: node.dependencies() for node in nodes}


def topological_order(nodes: tuple[NodeConfig, ...]) -> tuple[NodeConfig, ...]:
    dependencies = _dependencies_by_id(nodes)
    by_id = {node.node_id: node for node in nodes}
    order = topological_order_ids(by_id.keys(), dependencies)
    return tuple(by_id[node_id] for node_id in order)
