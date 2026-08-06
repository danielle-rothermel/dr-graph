from __future__ import annotations

import itertools

import pytest

from dr_graph.flow.transport import (
    InfeasibleTransportError,
    TransportProblem,
    solve_separable_transport,
)
from tests.flow.transport.support import cell, problem


def _minimum_cost_by_enumeration(
    transport_problem: TransportProblem,
) -> int | None:
    capacities = tuple(
        len(transport_cell.marginal_costs)
        for transport_cell in transport_problem.cells
    )
    minimum: int | None = None
    for cell_flows in itertools.product(
        *(range(capacity + 1) for capacity in capacities)
    ):
        source_totals = [0] * len(transport_problem.supplies)
        destination_totals = [0] * len(transport_problem.demands)
        total_cost = 0
        for transport_cell, flow in zip(
            transport_problem.cells,
            cell_flows,
            strict=True,
        ):
            source_totals[transport_cell.source_index] += flow
            destination_totals[transport_cell.destination_index] += flow
            total_cost += sum(transport_cell.marginal_costs[:flow])
        if tuple(source_totals) != transport_problem.supplies:
            continue
        if tuple(destination_totals) != transport_problem.demands:
            continue
        minimum = total_cost if minimum is None else min(minimum, total_cost)
    return minimum


def test_all_small_convex_transport_problems_match_enumeration() -> None:
    route_profiles = (None, (0,), (0, 1), (1, 1))
    cell_indexes = tuple(itertools.product(range(2), repeat=2))
    for supplies in itertools.product(range(2), repeat=2):
        for demands in itertools.product(range(2), repeat=2):
            if sum(supplies) != sum(demands):
                continue
            for cell_costs in itertools.product(route_profiles, repeat=4):
                cells = tuple(
                    cell(source_index, destination_index, *costs)
                    for (source_index, destination_index), costs in zip(
                        cell_indexes,
                        cell_costs,
                        strict=True,
                    )
                    if costs is not None
                )
                transport_problem = problem(supplies, demands, cells)
                expected_cost = _minimum_cost_by_enumeration(transport_problem)

                if expected_cost is None:
                    with pytest.raises(InfeasibleTransportError):
                        solve_separable_transport(transport_problem)
                else:
                    solution = solve_separable_transport(transport_problem)
                    assert solution.total_cost == expected_cost
