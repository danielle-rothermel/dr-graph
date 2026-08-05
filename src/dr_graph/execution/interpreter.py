from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dr_graph.execution.input_resolution import resolve_node_inputs
from dr_graph.execution.node_invocation import RunNode, invoke_node
from dr_graph.identity.graph_config import graph_hash
from dr_graph.results.continuation import validated_completed_outputs
from dr_graph.results.graph_runs import GraphRunResult, build_graph_run_result
from dr_graph.results.node_outcomes import (
    NodeOutcome,
    NodeOutcomeStatus,
    NodeOutput,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dr_graph.configuration.graphs import GraphConfig
    from dr_graph.configuration.nodes import NodeConfig


def execute_graph(
    *,
    graph: GraphConfig,
    inputs: Mapping[str, Any],
    run_node: RunNode,
    completed: Mapping[str, NodeOutput | Mapping[str, Any]] | None = None,
) -> GraphRunResult:
    computed_graph_hash = graph_hash(graph)
    completed_outputs = validated_completed_outputs(
        graph=graph,
        completed=completed,
    )
    outcomes: dict[str, NodeOutcome] = {}
    execution_order: list[str] = []

    for node in graph.topological_order():
        execution_order.append(node.node_id)
        if node.node_id in completed_outputs:
            outcomes[node.node_id] = NodeOutcome.success(
                node_id=node.node_id,
                output=completed_outputs[node.node_id],
            )
            continue
        blocked_by = _blocked_dependencies(node, outcomes)
        if blocked_by:
            outcomes[node.node_id] = NodeOutcome.blocked(
                node_id=node.node_id,
                blocked_by=blocked_by,
            )
            continue

        try:
            node_inputs = resolve_node_inputs(
                node=node,
                inputs=inputs,
                outcomes=outcomes,
                graph=graph,
            )
            output = invoke_node(
                node=node,
                node_inputs=node_inputs,
                run_node=run_node,
            )
        except Exception as error:  # noqa: BLE001 -- outcomes absorb node failures
            outcomes[node.node_id] = NodeOutcome.from_error(
                node_id=node.node_id,
                error=error,
            )
            continue

        outcomes[node.node_id] = NodeOutcome.success(
            node_id=node.node_id,
            output=output,
        )

    return build_graph_run_result(
        graph=graph,
        outcomes=outcomes,
        execution_order=tuple(execution_order),
        inputs=inputs,
        graph_hash_value=computed_graph_hash,
    )


def _blocked_dependencies(
    node: NodeConfig,
    outcomes: Mapping[str, NodeOutcome],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            dependency
            for dependency in node.dependencies()
            if outcomes[dependency].status is not NodeOutcomeStatus.SUCCESS
        )
    )
