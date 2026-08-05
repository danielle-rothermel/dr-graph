from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dr_graph.configuration.graphs import GraphConfig
from dr_graph.configuration.nodes import NodeConfig

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dr_graph.definitions.graphs import GraphDefinition


def materialize_graph_definition(
    definition: GraphDefinition,
    variable_assignments: Mapping[str, Mapping[str, Any]] | None = None,
) -> GraphConfig:
    assignments = variable_assignments or {}
    unknown = sorted(set(assignments) - set(definition.node_ids()))
    if unknown:
        joined = ", ".join(repr(node_id) for node_id in unknown)
        raise ValueError(
            f"variable assignment(s) {joined} reference unknown node id(s)"
        )
    nodes: list[NodeConfig] = []
    for node_definition in definition.nodes:
        values = dict(assignments.get(node_definition.node_id, {}))
        missing = sorted(node_definition.variable_names - set(values))
        if missing:
            joined = ", ".join(repr(name) for name in missing)
            raise ValueError(
                f"node {node_definition.node_id!r} is missing required "
                f"variable assignment(s) {joined}"
            )
        extra = sorted(set(values) - node_definition.variable_names)
        if extra:
            joined = ", ".join(repr(name) for name in extra)
            raise ValueError(
                f"node {node_definition.node_id!r} sets undeclared "
                f"variable(s) {joined}"
            )
        nodes.append(
            NodeConfig(
                node_id=node_definition.node_id,
                node_type=node_definition.node_type,
                fields=node_definition.fields,
                input_sources=dict(node_definition.input_sources),
                output_field=node_definition.output_field,
                variables=values,
            )
        )
    return GraphConfig(
        nodes=tuple(nodes),
        terminal_node_id=definition.terminal_node_id,
    )
