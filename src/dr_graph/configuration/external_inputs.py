from __future__ import annotations

from typing import TYPE_CHECKING

from dr_graph.core.errors import GraphValidationError
from dr_graph.core.input_sources import NodeInputSourceKind

if TYPE_CHECKING:
    from collections.abc import Collection

    from dr_graph.configuration.graphs import GraphConfig


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
