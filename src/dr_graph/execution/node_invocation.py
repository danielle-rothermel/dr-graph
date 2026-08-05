from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from dr_graph.configuration.nodes import NodeConfig
from dr_graph.core.errors import NodeExecutionError
from dr_graph.core.fields import missing_output_fields
from dr_graph.results.node_outcomes import NodeOutput

type RunNode = Callable[
    [NodeConfig, Mapping[str, Any]],
    NodeOutput | Mapping[str, Any],
]


def invoke_node(
    *,
    node: NodeConfig,
    node_inputs: Mapping[str, Any],
    run_node: RunNode,
) -> NodeOutput:
    output = NodeOutput.model_validate(run_node(node, node_inputs))
    missing = missing_output_fields(node.fields, output.values)
    if missing:
        joined = ", ".join(repr(field) for field in missing)
        raise NodeExecutionError(
            f"node {node.node_id!r} output missing field(s) {joined}"
        )
    return output
