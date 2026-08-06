from __future__ import annotations

from typing import cast

import pytest

from dr_graph.flow.transport import (
    FlowProblemError,
    InfeasibleTransportError,
    TransportProblem,
    TransportSolution,
    solve_separable_transport,
)
from tests.flow.transport.support import cell, problem


def test_one_to_one_transport_uses_each_marginal_unit() -> None:
    solution = solve_separable_transport(
        problem((3,), (3,), (cell(0, 0, 2, 4, 7),))
    )

    assert solution == TransportSolution(((3,),), 3, 13)


def test_multiple_sources_and_destinations_preserve_matrix_order() -> None:
    solution = solve_separable_transport(
        problem(
            (2, 1),
            (1, 2),
            (
                cell(0, 0, 5, 5),
                cell(0, 1, 1, 3),
                cell(1, 0, 1),
                cell(1, 1, 9),
            ),
        )
    )

    assert solution.allocations == ((0, 2), (1, 0))
    assert solution.total_flow == 3
    assert solution.total_cost == 5


def test_zero_total_returns_matrix_in_source_and_destination_shape() -> None:
    transport_problem = problem(
        (0, 0),
        (0, 0, 0),
        (cell(0, 1, 4),),
    )

    assert solve_separable_transport(transport_problem) == TransportSolution(
        ((0, 0, 0), (0, 0, 0)),
        0,
        0,
    )


def test_zero_supply_and_demand_rows_and_columns_remain_in_matrix() -> None:
    solution = solve_separable_transport(
        problem(
            (0, 2),
            (2, 0),
            (cell(0, 1, 0), cell(1, 0, 3, 4)),
        )
    )

    assert solution.allocations == ((0, 0), (2, 0))
    assert solution.total_cost == 7


def test_omitted_cell_is_unavailable() -> None:
    solution = solve_separable_transport(
        problem(
            (1, 1),
            (1, 1),
            (cell(0, 1, 2), cell(1, 0, 3)),
        )
    )

    assert solution.allocations == ((0, 1), (1, 0))
    assert solution.total_cost == 5


def test_residual_reassignment_finds_global_optimum() -> None:
    solution = solve_separable_transport(
        problem(
            (1, 1),
            (1, 1),
            (
                cell(0, 0, 0),
                cell(0, 1, 1),
                cell(1, 0, 1),
                cell(1, 1, 100),
            ),
        )
    )

    assert solution.allocations == ((0, 1), (1, 0))
    assert solution.total_cost == 2


def test_convex_costs_choose_lowest_global_marginal_units() -> None:
    solution = solve_separable_transport(
        problem(
            (3,),
            (2, 1),
            (cell(0, 0, 1, 9, 20), cell(0, 1, 2, 3)),
        )
    )

    assert solution.allocations == ((2, 1),)
    assert solution.total_cost == 12


def test_solver_rejects_non_transport_problem() -> None:
    with pytest.raises(FlowProblemError):
        solve_separable_transport(cast("TransportProblem", object()))


def test_infeasible_transport_raises_typed_error() -> None:
    transport_problem = problem(
        (1, 1),
        (1, 1),
        (cell(0, 0, 1, 2), cell(1, 0, 1, 2)),
    )

    with pytest.raises(InfeasibleTransportError):
        solve_separable_transport(transport_problem)
