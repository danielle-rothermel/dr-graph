from __future__ import annotations

import heapq
from dataclasses import dataclass

from dr_graph.flow.errors import (
    FlowPostconditionError,
    FlowProblemError,
    InfeasibleFlowError,
)
from dr_graph.flow.models import (
    ArcFlow,
    FlowProblem,
    FlowResult,
    NodeId,
)


@dataclass(slots=True)
class _ResidualArc:
    target_index: int
    reverse_index: int
    capacity: int
    cost: int
    declared_arc_index: int
    is_forward: bool


def solve_min_cost_flow(problem: FlowProblem) -> FlowResult:
    """Send exactly ``required_flow`` at minimum nonnegative integer cost.

    Equal-cost choices follow node declaration rank and residual adjacency
    order. Residual adjacency is derived from arc declaration order.
    """
    if not isinstance(problem, FlowProblem):
        raise FlowProblemError("problem must be a FlowProblem")

    node_indexes = {node: index for index, node in enumerate(problem.nodes)}
    residual = _build_residual_network(problem, node_indexes)
    source_index = node_indexes[problem.source]
    sink_index = node_indexes[problem.sink]
    potentials = [0] * len(problem.nodes)
    arc_flows = [0] * len(problem.arcs)
    sent_flow = 0
    total_cost = 0

    while sent_flow < problem.required_flow:
        distances, predecessors = _shortest_residual_paths(
            residual,
            source_index,
            potentials,
        )
        if distances[sink_index] is None:
            raise InfeasibleFlowError(
                "network cannot carry the exact required flow: "
                f"sent {sent_flow} of {problem.required_flow}"
            )

        for node_index, distance in enumerate(distances):
            if distance is not None:
                potentials[node_index] += distance

        augmentation = problem.required_flow - sent_flow
        cursor = sink_index
        while cursor != source_index:
            predecessor = predecessors[cursor]
            if predecessor is None:
                raise FlowPostconditionError(
                    "reachable sink has no residual predecessor path"
                )
            previous, residual_index = predecessor
            augmentation = min(
                augmentation,
                residual[previous][residual_index].capacity,
            )
            cursor = previous

        path_cost = 0
        cursor = sink_index
        while cursor != source_index:
            predecessor = predecessors[cursor]
            if predecessor is None:
                raise FlowPostconditionError(
                    "reachable sink has no residual predecessor path"
                )
            previous, residual_index = predecessor
            edge = residual[previous][residual_index]
            reverse = residual[edge.target_index][edge.reverse_index]
            edge.capacity -= augmentation
            reverse.capacity += augmentation
            direction = 1 if edge.is_forward else -1
            arc_flows[edge.declared_arc_index] += direction * augmentation
            path_cost += edge.cost
            cursor = previous

        sent_flow += augmentation
        total_cost += augmentation * path_cost

    result = FlowResult(
        sent_flow=sent_flow,
        total_cost=total_cost,
        arc_flows=tuple(
            ArcFlow(arc_id=arc.arc_id, flow=flow)
            for arc, flow in zip(problem.arcs, arc_flows, strict=True)
        ),
    )
    _validate_result(problem, result)
    return result


def _build_residual_network(
    problem: FlowProblem,
    node_indexes: dict[NodeId, int],
) -> list[list[_ResidualArc]]:
    residual: list[list[_ResidualArc]] = [[] for _node in problem.nodes]
    for arc_index, arc in enumerate(problem.arcs):
        source_index = node_indexes[arc.source]
        target_index = node_indexes[arc.target]
        forward_index = len(residual[source_index])
        residual[source_index].append(
            _ResidualArc(
                target_index=target_index,
                reverse_index=-1,
                capacity=arc.capacity,
                cost=arc.unit_cost,
                declared_arc_index=arc_index,
                is_forward=True,
            )
        )
        reverse_index = len(residual[target_index])
        residual[target_index].append(
            _ResidualArc(
                target_index=source_index,
                reverse_index=forward_index,
                capacity=0,
                cost=-arc.unit_cost,
                declared_arc_index=arc_index,
                is_forward=False,
            )
        )
        residual[source_index][forward_index].reverse_index = reverse_index
    return residual


def _shortest_residual_paths(
    residual: list[list[_ResidualArc]],
    source_index: int,
    potentials: list[int],
) -> tuple[list[int | None], list[tuple[int, int] | None]]:
    distances: list[int | None] = [None] * len(residual)
    predecessors: list[tuple[int, int] | None] = [None] * len(residual)
    distances[source_index] = 0
    heap = [(0, source_index)]

    while heap:
        distance, node_index = heapq.heappop(heap)
        if distances[node_index] != distance:
            continue
        for residual_index, edge in enumerate(residual[node_index]):
            if edge.capacity == 0:
                continue
            reduced_cost = (
                edge.cost
                + potentials[node_index]
                - potentials[edge.target_index]
            )
            candidate = distance + reduced_cost
            known = distances[edge.target_index]
            if known is not None and candidate >= known:
                continue
            distances[edge.target_index] = candidate
            predecessors[edge.target_index] = (
                node_index,
                residual_index,
            )
            heapq.heappush(heap, (candidate, edge.target_index))

    return distances, predecessors


def _validate_result(problem: FlowProblem, result: FlowResult) -> None:
    if result.sent_flow != problem.required_flow:
        raise FlowPostconditionError(
            "solver did not send the exact required flow"
        )
    if len(result.arc_flows) != len(problem.arcs):
        raise FlowPostconditionError(
            "solver did not return every declared arc"
        )

    balance = dict.fromkeys(problem.nodes, 0)
    recomputed_cost = 0
    for arc, arc_flow in zip(
        problem.arcs,
        result.arc_flows,
        strict=True,
    ):
        if arc_flow.arc_id != arc.arc_id:
            raise FlowPostconditionError(
                "solver returned arc flows out of declaration order"
            )
        if arc_flow.flow < 0 or arc_flow.flow > arc.capacity:
            raise FlowPostconditionError(
                f"flow for arc {arc.arc_id!r} violates its capacity"
            )
        balance[arc.source] += arc_flow.flow
        balance[arc.target] -= arc_flow.flow
        recomputed_cost += arc_flow.flow * arc.unit_cost

    if balance[problem.source] != result.sent_flow:
        raise FlowPostconditionError("source balance does not match sent flow")
    if balance[problem.sink] != -result.sent_flow:
        raise FlowPostconditionError("sink balance does not match sent flow")
    for node, node_balance in balance.items():
        if node not in (problem.source, problem.sink) and node_balance != 0:
            raise FlowPostconditionError(
                f"flow is not conserved at node {node!r}"
            )
    if recomputed_cost != result.total_cost:
        raise FlowPostconditionError("total cost does not match per-arc flow")
