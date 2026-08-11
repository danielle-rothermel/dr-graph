from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from dr_graph.core.interruption import GraphRunInterruptedError
from dr_graph.core.json_values import strict_json_object
from dr_graph.execution.input_resolution import resolve_node_inputs
from dr_graph.execution.node_invocation import RunNode, invoke_node
from dr_graph.identity.graph_config import graph_hash
from dr_graph.results.continuation import validated_completed_outputs
from dr_graph.results.graph_runs import GraphRunResult, build_graph_run_result
from dr_graph.results.node_outcomes import (
    NodeOutcome,
    NodeOutcomeSource,
    NodeOutcomeStatus,
    NodeOutput,
)

_INTERRUPTION_TYPES = (asyncio.CancelledError, KeyboardInterrupt)

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
    external_inputs = deepcopy(strict_json_object(dict(inputs)))
    completed_outputs = validated_completed_outputs(
        graph=graph,
        completed=completed,
    )
    outcomes: dict[str, NodeOutcome] = {}
    execution_order: list[str] = []
    ordered_nodes = list(graph.topological_order())

    for node in ordered_nodes:
        execution_order.append(node.node_id)
        if node.node_id in completed_outputs:
            outcomes[node.node_id] = NodeOutcome.success(
                node_id=node.node_id,
                output=completed_outputs[node.node_id],
                outcome_source=NodeOutcomeSource.REUSED,
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
        except _INTERRUPTION_TYPES as interruption:
            outcomes[node.node_id] = NodeOutcome.cancelled(
                node_id=node.node_id,
            )
            _block_remaining_nodes(
                ordered_nodes=ordered_nodes,
                cancelled_node_id=node.node_id,
                completed_outputs=completed_outputs,
                outcomes=outcomes,
                execution_order=execution_order,
            )
            partial_result = build_graph_run_result(
                graph=graph,
                outcomes=outcomes,
                execution_order=tuple(execution_order),
                inputs=external_inputs,
                graph_hash_value=computed_graph_hash,
            )
            raise GraphRunInterruptedError(
                f"graph run interrupted at node {node.node_id!r}",
                partial_result=partial_result,
            ) from interruption
        except Exception as error:  # noqa: BLE001 -- converted to a node outcome
            outcomes[node.node_id] = NodeOutcome.from_error(
                node_id=node.node_id,
                error=error,
            )
            continue

        outcomes[node.node_id] = NodeOutcome.success(
            node_id=node.node_id,
            output=output,
            outcome_source=NodeOutcomeSource.FRESH,
        )

    return build_graph_run_result(
        graph=graph,
        outcomes=outcomes,
        execution_order=tuple(execution_order),
        inputs=external_inputs,
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


def _block_remaining_nodes(
    *,
    ordered_nodes: list[NodeConfig],
    cancelled_node_id: str,
    completed_outputs: dict[str, NodeOutput],
    outcomes: dict[str, NodeOutcome],
    execution_order: list[str],
) -> None:
    seen = set(outcomes)
    for remaining in ordered_nodes:
        if remaining.node_id in seen:
            continue
        execution_order.append(remaining.node_id)
        if remaining.node_id in completed_outputs:
            outcomes[remaining.node_id] = NodeOutcome.success(
                node_id=remaining.node_id,
                output=completed_outputs[remaining.node_id],
                outcome_source=NodeOutcomeSource.REUSED,
            )
            continue
        blocked_by = _blocked_dependencies(remaining, outcomes)
        if not blocked_by:
            blocked_by = (cancelled_node_id,)
        outcomes[remaining.node_id] = NodeOutcome.blocked(
            node_id=remaining.node_id,
            blocked_by=blocked_by,
        )
