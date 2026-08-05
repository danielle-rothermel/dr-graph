from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dr_graph.core.errors import InputResolutionError
from dr_graph.core.input_sources import NodeInputSourceKind
from dr_graph.results.node_outcomes import NodeOutcome, NodeOutcomeStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dr_graph.configuration.graphs import GraphConfig
    from dr_graph.configuration.nodes import NodeConfig


def resolve_node_inputs(
    *,
    node: NodeConfig,
    inputs: Mapping[str, Any],
    outcomes: Mapping[str, NodeOutcome],
    graph: GraphConfig,
) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for field_name, ref in node.input_sources.items():
        if ref.kind is NodeInputSourceKind.GRAPH_EXTERNAL:
            if ref.field is None or ref.field not in inputs:
                raise InputResolutionError(
                    f"missing external input {ref.field!r} "
                    f"for node {node.node_id!r}"
                )
            resolved[field_name] = inputs[ref.field]
            continue

        if ref.node_id is None:
            raise InputResolutionError(
                f"node input source {ref.ref!r} has no node id"
            )
        upstream = outcomes.get(ref.node_id)
        if (
            upstream is None
            or upstream.status is not NodeOutcomeStatus.SUCCESS
        ):
            raise InputResolutionError(
                f"upstream node {ref.node_id!r} did not succeed"
            )
        if upstream.output is None:
            raise InputResolutionError(
                f"upstream node {ref.node_id!r} has no output"
            )
        output_field = ref.field or graph.node(ref.node_id).output_field
        if output_field not in upstream.output.values:
            raise InputResolutionError(
                f"upstream node {ref.node_id!r} output missing "
                f"field {output_field!r}"
            )
        resolved[field_name] = upstream.output.values[output_field]
    return resolved
