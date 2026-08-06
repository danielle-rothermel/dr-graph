from __future__ import annotations

import heapq
from dataclasses import dataclass

from dr_graph.flow.errors import FlowPostconditionError, FlowProblemError
from dr_graph.flow.transport.errors import InfeasibleTransportError
from dr_graph.flow.transport.models import (
    TransportCell,
    TransportProblem,
    TransportSolution,
)


@dataclass(slots=True)
class _ResidualArc:
    target_index: int
    reverse_index: int
    capacity: int
    cost: int
    cell_index: int | None
    is_forward: bool


@dataclass(slots=True)
class _CellState:
    marginal_costs: tuple[int, ...]
    flow: int
    forward: _ResidualArc
    reverse: _ResidualArc


def solve_separable_transport(
    problem: TransportProblem,
) -> TransportSolution:
    """Return the exact minimum-cost allocation for a balanced problem."""
    if not isinstance(problem, TransportProblem):
        raise FlowProblemError("problem must be a TransportProblem")

    empty_allocations = tuple(
        tuple(0 for _demand in problem.demands) for _supply in problem.supplies
    )
    required_flow = sum(problem.supplies)
    if required_flow == 0:
        result = TransportSolution(
            allocations=empty_allocations,
            total_flow=0,
            total_cost=0,
        )
        _validate_solution(problem, result)
        return result

    residual, cell_states, source_index, sink_index = _build_residual_network(
        problem
    )
    potentials = [0] * len(residual)
    sent_flow = 0
    total_cost = 0

    while sent_flow < required_flow:
        distances, predecessors = _shortest_residual_paths(
            residual,
            source_index,
            potentials,
        )
        if distances[sink_index] is None:
            raise InfeasibleTransportError(
                "transport network cannot satisfy every supply and demand"
            )

        for node_index, distance in enumerate(distances):
            if distance is not None:
                potentials[node_index] += distance

        augmentation = required_flow - sent_flow
        cursor = sink_index
        while cursor != source_index:
            previous, residual_index = _require_predecessor(
                predecessors,
                cursor,
            )
            augmentation = min(
                augmentation,
                residual[previous][residual_index].capacity,
            )
            cursor = previous

        path_cost = 0
        cursor = sink_index
        while cursor != source_index:
            previous, residual_index = _require_predecessor(
                predecessors,
                cursor,
            )
            edge = residual[previous][residual_index]
            path_cost += edge.cost
            if edge.cell_index is None:
                reverse = residual[edge.target_index][edge.reverse_index]
                edge.capacity -= augmentation
                reverse.capacity += augmentation
            else:
                if augmentation != 1:
                    raise FlowPostconditionError(
                        "convex cell residual must augment one unit at a time"
                    )
                cell_state = cell_states[edge.cell_index]
                cell_state.flow += 1 if edge.is_forward else -1
                _refresh_cell_state(cell_state)
            cursor = previous

        sent_flow += augmentation
        total_cost += augmentation * path_cost

    allocations = [list(row) for row in empty_allocations]
    for cell, cell_state in zip(problem.cells, cell_states, strict=True):
        allocations[cell.source_index][cell.destination_index] = (
            cell_state.flow
        )

    result = TransportSolution(
        allocations=tuple(tuple(row) for row in allocations),
        total_flow=sent_flow,
        total_cost=total_cost,
    )
    _validate_solution(problem, result)
    return result


def _build_residual_network(
    problem: TransportProblem,
) -> tuple[list[list[_ResidualArc]], list[_CellState], int, int]:
    source_index = 0
    first_supply_index = 1
    first_demand_index = first_supply_index + len(problem.supplies)
    sink_index = first_demand_index + len(problem.demands)
    residual: list[list[_ResidualArc]] = [
        [] for _node_index in range(sink_index + 1)
    ]

    for supply_index, supply in enumerate(problem.supplies):
        _add_linear_edge(
            residual,
            source_index,
            first_supply_index + supply_index,
            capacity=supply,
        )

    cell_states: list[_CellState] = []
    for cell in problem.cells:
        cell_states.append(
            _add_cell_edge(
                residual,
                first_supply_index + cell.source_index,
                first_demand_index + cell.destination_index,
                cell,
                cell_index=len(cell_states),
            )
        )

    for demand_index, demand in enumerate(problem.demands):
        _add_linear_edge(
            residual,
            first_demand_index + demand_index,
            sink_index,
            capacity=demand,
        )

    return residual, cell_states, source_index, sink_index


def _add_linear_edge(
    residual: list[list[_ResidualArc]],
    source_index: int,
    target_index: int,
    *,
    capacity: int,
) -> None:
    forward_index = len(residual[source_index])
    reverse_index = len(residual[target_index])
    residual[source_index].append(
        _ResidualArc(
            target_index=target_index,
            reverse_index=reverse_index,
            capacity=capacity,
            cost=0,
            cell_index=None,
            is_forward=True,
        )
    )
    residual[target_index].append(
        _ResidualArc(
            target_index=source_index,
            reverse_index=forward_index,
            capacity=0,
            cost=0,
            cell_index=None,
            is_forward=False,
        )
    )


def _add_cell_edge(
    residual: list[list[_ResidualArc]],
    source_index: int,
    target_index: int,
    cell: TransportCell,
    *,
    cell_index: int,
) -> _CellState:
    forward_index = len(residual[source_index])
    reverse_index = len(residual[target_index])
    forward = _ResidualArc(
        target_index=target_index,
        reverse_index=reverse_index,
        capacity=1,
        cost=cell.marginal_costs[0],
        cell_index=cell_index,
        is_forward=True,
    )
    reverse = _ResidualArc(
        target_index=source_index,
        reverse_index=forward_index,
        capacity=0,
        cost=0,
        cell_index=cell_index,
        is_forward=False,
    )
    residual[source_index].append(forward)
    residual[target_index].append(reverse)
    return _CellState(
        marginal_costs=cell.marginal_costs,
        flow=0,
        forward=forward,
        reverse=reverse,
    )


def _refresh_cell_state(cell_state: _CellState) -> None:
    flow = cell_state.flow
    if flow < 0 or flow > len(cell_state.marginal_costs):
        raise FlowPostconditionError(
            "convex cell residual flow violates its capacity"
        )

    cell_state.forward.capacity = int(flow < len(cell_state.marginal_costs))
    if cell_state.forward.capacity:
        cell_state.forward.cost = cell_state.marginal_costs[flow]

    cell_state.reverse.capacity = int(flow > 0)
    if cell_state.reverse.capacity:
        cell_state.reverse.cost = -cell_state.marginal_costs[flow - 1]


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


def _require_predecessor(
    predecessors: list[tuple[int, int] | None],
    node_index: int,
) -> tuple[int, int]:
    predecessor = predecessors[node_index]
    if predecessor is None:
        raise FlowPostconditionError(
            "reachable transport sink has no residual predecessor path"
        )
    return predecessor


def _validate_solution(
    problem: TransportProblem,
    result: TransportSolution,
) -> None:
    if result.total_flow != sum(problem.supplies):
        raise FlowPostconditionError(
            "transport solver did not allocate every supplied unit"
        )
    if len(result.allocations) != len(problem.supplies):
        raise FlowPostconditionError(
            "transport allocation row count does not match supplies"
        )
    if any(len(row) != len(problem.demands) for row in result.allocations):
        raise FlowPostconditionError(
            "transport allocation column count does not match demands"
        )

    cells_by_pair = {
        (cell.source_index, cell.destination_index): cell
        for cell in problem.cells
    }
    recomputed_cost = 0
    for source_index, (supply, row) in enumerate(
        zip(problem.supplies, result.allocations, strict=True)
    ):
        if sum(row) != supply:
            raise FlowPostconditionError(
                "transport allocation row does not match its supply"
            )
        for destination_index, allocation in enumerate(row):
            cell = cells_by_pair.get((source_index, destination_index))
            capacity = 0 if cell is None else len(cell.marginal_costs)
            if allocation < 0 or allocation > capacity:
                raise FlowPostconditionError(
                    "transport allocation violates its cell capacity"
                )
            if cell is not None:
                recomputed_cost += sum(cell.marginal_costs[:allocation])

    for destination_index, demand in enumerate(problem.demands):
        if sum(row[destination_index] for row in result.allocations) != demand:
            raise FlowPostconditionError(
                "transport allocation column does not match its demand"
            )
    if recomputed_cost != result.total_cost:
        raise FlowPostconditionError(
            "transport total cost does not match its allocations"
        )
