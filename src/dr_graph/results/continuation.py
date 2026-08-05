from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from dr_graph.core.errors import CompletedNodeError
from dr_graph.core.fields import missing_output_fields
from dr_graph.results.node_outcomes import NodeOutput

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dr_graph.configuration.graphs import GraphConfig


def validated_completed_outputs(
    *,
    graph: GraphConfig,
    completed: Mapping[str, NodeOutput | Mapping[str, Any]] | None,
) -> dict[str, NodeOutput]:
    if not completed:
        return {}
    node_ids = set(graph.node_ids())
    outputs: dict[str, NodeOutput] = {}
    for node_id, raw_output in completed.items():
        if node_id not in node_ids:
            raise CompletedNodeError(
                f"completed node {node_id!r} is not in the graph"
            )
        try:
            output = NodeOutput.model_validate(raw_output)
        except ValidationError as error:
            raise CompletedNodeError(
                f"completed output for node {node_id!r} is invalid: {error}"
            ) from error
        missing = missing_output_fields(
            graph.node(node_id).fields,
            output.values,
        )
        if missing:
            joined = ", ".join(repr(field) for field in missing)
            raise CompletedNodeError(
                f"completed output for node {node_id!r} missing "
                f"field(s) {joined}"
            )
        outputs[node_id] = output
    completed_ids = outputs.keys()
    for node_id in outputs:
        missing_dependencies = sorted(
            graph.node(node_id).dependencies() - completed_ids
        )
        if missing_dependencies:
            joined = ", ".join(repr(item) for item in missing_dependencies)
            raise CompletedNodeError(
                f"completed node {node_id!r} requires completed node(s) "
                f"{joined}"
            )
    return outputs
