from __future__ import annotations

from typing import TYPE_CHECKING

from dr_graph.errors import GraphValidationError
from dr_graph.refs import BindingSource

if TYPE_CHECKING:
    from collections.abc import Collection

    from dr_graph.refs import BindingRef
    from dr_graph.spec import GraphSpec, NodeSpec


def validate_graph_spec(graph: GraphSpec) -> None:
    if not graph.nodes:
        raise GraphValidationError("graph must have at least one node")
    node_ids = graph.node_ids()
    if len(node_ids) != len(set(node_ids)):
        raise GraphValidationError("duplicate node ids")
    nodes_by_id = {node.id: node for node in graph.nodes}
    if graph.terminal_node_id not in nodes_by_id:
        raise GraphValidationError(
            f"terminal_node_id {graph.terminal_node_id!r} not in graph"
        )
    for node in graph.nodes:
        for ref in node.config.input_bindings.values():
            validate_binding_ref(ref, nodes_by_id)
    validate_acyclic_graph(graph.nodes)


def external_binding_fields(graph: GraphSpec) -> frozenset[str]:
    return frozenset(
        ref.field
        for node in graph.nodes
        for ref in node.config.input_bindings.values()
        if ref.source is BindingSource.EXTERNAL and ref.field is not None
    )


def validate_external_bindings(
    graph: GraphSpec,
    *,
    allowed_fields: Collection[str],
) -> None:
    bound = external_binding_fields(graph)
    if not bound:
        return
    allowed = set(allowed_fields)
    unknown = sorted(bound - allowed)
    if unknown:
        unknown_list = ", ".join(repr(field) for field in unknown)
        raise GraphValidationError(
            f"external binding field(s) {unknown_list} not in allowed "
            "external fields"
        )


def validate_binding_ref(
    ref: BindingRef,
    nodes_by_id: dict[str, NodeSpec],
) -> None:
    if ref.source is BindingSource.EXTERNAL:
        return
    if ref.node_id not in nodes_by_id:
        raise GraphValidationError(
            f"ref {ref.ref!r} points at unknown node {ref.node_id!r}"
        )
    if ref.field is None:
        return
    source_node = nodes_by_id[ref.node_id]
    output_names = {field.name for field in source_node.config.output_fields()}
    if ref.field not in output_names:
        raise GraphValidationError(
            f"ref {ref.ref!r} points at unknown field {ref.field!r} "
            f"on node {ref.node_id!r}"
        )


def validate_acyclic_graph(nodes: tuple[NodeSpec, ...]) -> None:
    topological_order(nodes)


def topological_order(nodes: tuple[NodeSpec, ...]) -> tuple[NodeSpec, ...]:
    node_ids = {node.id for node in nodes}
    by_id = {node.id: node for node in nodes}
    done: set[str] = set()
    remaining = set(node_ids)
    ordered: list[NodeSpec] = []
    while remaining:
        ready = sorted(
            node_id
            for node_id in remaining
            if by_id[node_id].dependencies() <= done
        )
        if not ready:
            stuck = ", ".join(sorted(remaining))
            raise GraphValidationError(f"graph has a cycle among: {stuck}")
        ordered.extend(by_id[node_id] for node_id in ready)
        done.update(ready)
        remaining.difference_update(ready)
    return tuple(ordered)
