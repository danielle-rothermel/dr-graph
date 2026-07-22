from __future__ import annotations

from typing import TYPE_CHECKING

from dr_graph.errors import GraphValidationError
from dr_graph.refs import NodeInputSourceKind

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from dr_graph.refs import NodeInputSourceRef
    from dr_graph.spec import GraphConfig, NodeConfig


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
    for node in graph.nodes:
        for ref in node.input_sources.values():
            validate_node_input_source(ref, nodes_by_id)
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


def validate_single_terminal_ids(
    node_ids: Collection[str],
    dependencies: Mapping[str, Collection[str]],
    *,
    terminal_node_id: str,
) -> None:
    """Exactly one terminal/sink Node: no other node consumes its output."""
    consumed = {dep for deps in dependencies.values() for dep in deps}
    if terminal_node_id in consumed:
        raise GraphValidationError(
            f"terminal node {terminal_node_id!r} is consumed by another "
            "node and cannot be the sink"
        )
    other_sinks = sorted(
        node_id
        for node_id in node_ids
        if node_id not in consumed and node_id != terminal_node_id
    )
    if other_sinks:
        joined = ", ".join(repr(node_id) for node_id in other_sinks)
        raise GraphValidationError(
            f"graph has more than one terminal/sink node: "
            f"{terminal_node_id!r} and {joined}"
        )


def external_input_fields(graph: GraphConfig) -> frozenset[str]:
    return frozenset(
        ref.field
        for node in graph.nodes
        for ref in node.input_sources.values()
        if ref.kind is NodeInputSourceKind.GRAPH_EXTERNAL
        and ref.field is not None
    )


def validate_graph_external_inputs(
    graph: GraphConfig,
    *,
    allowed_fields: Collection[str],
) -> None:
    bound = external_input_fields(graph)
    if not bound:
        return
    allowed = set(allowed_fields)
    unknown = sorted(bound - allowed)
    if unknown:
        unknown_list = ", ".join(repr(field) for field in unknown)
        raise GraphValidationError(
            f"graph external input(s) {unknown_list} not in allowed "
            "external fields"
        )


def validate_node_input_source(
    ref: NodeInputSourceRef,
    nodes_by_id: dict[str, NodeConfig],
) -> None:
    if ref.kind is NodeInputSourceKind.GRAPH_EXTERNAL:
        return
    if ref.node_id not in nodes_by_id:
        raise GraphValidationError(
            f"input source {ref.ref!r} points at unknown node "
            f"{ref.node_id!r}"
        )
    if ref.field is None:
        return
    source_node = nodes_by_id[ref.node_id]
    output_names = {field.name for field in source_node.output_fields()}
    if ref.field not in output_names:
        raise GraphValidationError(
            f"input source {ref.ref!r} points at unknown field "
            f"{ref.field!r} on node {ref.node_id!r}"
        )


def topological_order(nodes: tuple[NodeConfig, ...]) -> tuple[NodeConfig, ...]:
    dependencies = _dependencies_by_id(nodes)
    by_id = {node.node_id: node for node in nodes}
    order = topological_order_ids(by_id.keys(), dependencies)
    return tuple(by_id[node_id] for node_id in order)


def topological_order_ids(
    node_ids: Collection[str],
    dependencies: Mapping[str, Collection[str]],
) -> tuple[str, ...]:
    done: set[str] = set()
    remaining = set(node_ids)
    ordered: list[str] = []
    while remaining:
        ready = sorted(
            node_id
            for node_id in remaining
            if set(dependencies.get(node_id, ())) <= done
        )
        if not ready:
            stuck = ", ".join(sorted(remaining))
            raise GraphValidationError(f"graph has a cycle among: {stuck}")
        ordered.extend(ready)
        done.update(ready)
        remaining.difference_update(ready)
    return tuple(ordered)
