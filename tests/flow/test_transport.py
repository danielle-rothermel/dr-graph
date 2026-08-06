from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

import dr_graph
import dr_graph.flow
from dr_graph.flow import transport
from dr_graph.flow.errors import FlowProblemError
from dr_graph.flow.transport import (
    InfeasibleTransportError,
    TransportCell,
    TransportProblem,
    TransportSolution,
    solve_separable_transport,
)
from dr_graph.flow.transport.solver import _build_residual_network


def _problem(
    supplies: tuple[int, ...],
    demands: tuple[int, ...],
    cells: tuple[TransportCell, ...],
) -> TransportProblem:
    return TransportProblem(
        supplies=supplies,
        demands=demands,
        cells=cells,
    )


def _cell(
    source_index: int,
    destination_index: int,
    *marginal_costs: int,
) -> TransportCell:
    return TransportCell(
        source_index=source_index,
        destination_index=destination_index,
        marginal_costs=marginal_costs,
    )


def _assign_attribute(value: object, name: str, replacement: object) -> None:
    setattr(value, name, replacement)


def test_transport_api_stays_in_explicit_transport_module() -> None:
    assert not hasattr(dr_graph, "TransportProblem")
    assert not hasattr(dr_graph.flow, "TransportProblem")
    assert not hasattr(transport, "FlowProblem")
    assert not hasattr(transport, "solve_min_cost_flow")
    assert transport.__all__ == [
        "InfeasibleTransportError",
        "TransportCell",
        "TransportProblem",
        "TransportSolution",
        "solve_separable_transport",
    ]


def test_one_to_one_transport_uses_each_marginal_unit() -> None:
    solution = solve_separable_transport(
        _problem((3,), (3,), (_cell(0, 0, 2, 4, 7),))
    )

    assert solution == TransportSolution(
        allocations=((3,),),
        total_flow=3,
        total_cost=13,
    )


def test_multiple_sources_and_destinations_preserve_matrix_order() -> None:
    solution = solve_separable_transport(
        _problem(
            (2, 1),
            (1, 2),
            (
                _cell(0, 0, 5, 5),
                _cell(0, 1, 1, 3),
                _cell(1, 0, 1),
                _cell(1, 1, 9),
            ),
        )
    )

    assert solution.allocations == ((0, 2), (1, 0))
    assert solution.total_flow == 3
    assert solution.total_cost == 5


def test_zero_total_returns_shaped_zero_matrix_without_solving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = _problem(
        (0, 0),
        (0, 0, 0),
        (_cell(0, 1, 4),),
    )

    def fail_if_called(_problem: object) -> None:
        pytest.fail("zero-total transport must not build a residual network")

    monkeypatch.setattr(
        "dr_graph.flow.transport.solver._build_residual_network",
        fail_if_called,
    )

    assert solve_separable_transport(problem) == TransportSolution(
        allocations=((0, 0, 0), (0, 0, 0)),
        total_flow=0,
        total_cost=0,
    )


def test_zero_supply_and_demand_rows_and_columns_remain_in_matrix() -> None:
    solution = solve_separable_transport(
        _problem(
            (0, 2),
            (2, 0),
            (
                _cell(0, 1, 0),
                _cell(1, 0, 3, 4),
            ),
        )
    )

    assert solution.allocations == ((0, 0), (2, 0))
    assert solution.total_cost == 7


def test_omitted_cell_is_unavailable() -> None:
    solution = solve_separable_transport(
        _problem(
            (1, 1),
            (1, 1),
            (
                _cell(0, 1, 2),
                _cell(1, 0, 3),
            ),
        )
    )

    assert solution.allocations == ((0, 1), (1, 0))
    assert solution.total_cost == 5


def test_parallel_marginal_units_have_independent_costs() -> None:
    solution = solve_separable_transport(
        _problem(
            (2,),
            (1, 1),
            (
                _cell(0, 0, 1, 100),
                _cell(0, 1, 5),
            ),
        )
    )

    assert solution.allocations == ((1, 1),)
    assert solution.total_cost == 6


def test_residual_reassignment_finds_global_optimum() -> None:
    solution = solve_separable_transport(
        _problem(
            (1, 1),
            (1, 1),
            (
                _cell(0, 0, 0),
                _cell(0, 1, 1),
                _cell(1, 0, 1),
                _cell(1, 1, 100),
            ),
        )
    )

    assert solution.allocations == ((0, 1), (1, 0))
    assert solution.total_cost == 2


def test_convex_costs_choose_lowest_global_marginal_units() -> None:
    solution = solve_separable_transport(
        _problem(
            (3,),
            (2, 1),
            (
                _cell(0, 0, 1, 9, 20),
                _cell(0, 1, 2, 3),
            ),
        )
    )

    assert solution.allocations == ((2, 1),)
    assert solution.total_cost == 12


def test_convex_cell_uses_constant_residual_edges() -> None:
    marginal_costs = tuple(range(1_000))
    problem = _problem(
        (len(marginal_costs),),
        (len(marginal_costs),),
        (_cell(0, 0, *marginal_costs),),
    )

    residual, cell_states, _source_index, _sink_index = (
        _build_residual_network(problem)
    )

    assert sum(len(edges) for edges in residual) == 6
    assert len(cell_states) == 1
    assert solve_separable_transport(problem) == TransportSolution(
        allocations=((1_000,),),
        total_flow=1_000,
        total_cost=sum(marginal_costs),
    )


def test_equal_cost_ties_follow_ordered_source_inputs() -> None:
    solution = solve_separable_transport(
        _problem(
            (1, 1),
            (1, 1),
            (
                _cell(0, 0, 4),
                _cell(0, 1, 4),
                _cell(1, 0, 4),
                _cell(1, 1, 4),
            ),
        )
    )

    assert solution.allocations == ((1, 0), (0, 1))
    assert solution.total_cost == 8


def test_problem_copies_caller_owned_collections() -> None:
    supplies = [1]
    demands = [1]
    cells = [_cell(0, 0, 2)]

    problem = TransportProblem(
        supplies=cast("tuple[int, ...]", supplies),
        demands=cast("tuple[int, ...]", demands),
        cells=cast("tuple[TransportCell, ...]", cells),
    )
    supplies.clear()
    demands.clear()
    cells.clear()

    assert problem == _problem((1,), (1,), (_cell(0, 0, 2),))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("supplies", {1}),
        ("demands", {1}),
        ("cells", set()),
    ],
)
def test_problem_rejects_unordered_collections(
    field: str,
    value: object,
) -> None:
    supplies = cast("tuple[int, ...]", value) if field == "supplies" else (1,)
    demands = cast("tuple[int, ...]", value) if field == "demands" else (1,)
    cells = (
        cast("tuple[TransportCell, ...]", value)
        if field == "cells"
        else (_cell(0, 0, 1),)
    )

    with pytest.raises(FlowProblemError, match="tuple or list"):
        _problem(supplies, demands, cells)


def test_solution_copies_caller_owned_allocations() -> None:
    allocations = [[1]]

    solution = TransportSolution(
        allocations=cast("tuple[tuple[int, ...], ...]", allocations),
        total_flow=1,
        total_cost=2,
    )
    allocations[0].clear()
    allocations.clear()

    assert solution.allocations == ((1,),)


def test_transport_values_are_frozen_and_slotted() -> None:
    cell = _cell(0, 0, 1)
    problem = _problem((1,), (1,), (cell,))
    solution = solve_separable_transport(problem)

    with pytest.raises(FrozenInstanceError):
        _assign_attribute(cell, "source_index", 1)
    with pytest.raises(FrozenInstanceError):
        _assign_attribute(problem, "supplies", (2,))
    with pytest.raises(FrozenInstanceError):
        _assign_attribute(solution, "total_flow", 2)

    assert not hasattr(cell, "__dict__")
    assert not hasattr(problem, "__dict__")
    assert not hasattr(solution, "__dict__")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("supply", -1),
        ("supply", True),
        ("supply", 1.0),
        ("demand", -1),
        ("demand", False),
        ("demand", 1.0),
    ],
)
def test_problem_rejects_invalid_supply_and_demand_values(
    field: str,
    value: object,
) -> None:
    supplies = (cast("int", value),) if field == "supply" else (0,)
    demands = (cast("int", value),) if field == "demand" else (0,)

    with pytest.raises(FlowProblemError, match=field):
        _problem(supplies, demands, ())


def test_problem_rejects_unbalanced_totals() -> None:
    with pytest.raises(FlowProblemError, match="total supply"):
        _problem((1,), (0,), ())


@pytest.mark.parametrize(
    ("source_index", "destination_index", "match"),
    [
        (-1, 0, "source_index"),
        (True, 0, "source_index"),
        (0.0, 0, "source_index"),
        (0, -1, "destination_index"),
        (0, False, "destination_index"),
        (0, 0.0, "destination_index"),
    ],
)
def test_cell_rejects_invalid_indexes(
    source_index: object,
    destination_index: object,
    match: str,
) -> None:
    with pytest.raises(FlowProblemError, match=match):
        _cell(
            cast("int", source_index),
            cast("int", destination_index),
            1,
        )


@pytest.mark.parametrize(
    ("cell", "match"),
    [
        (_cell(1, 0, 1), "source_index.*out of range"),
        (_cell(0, 1, 1), "destination_index.*out of range"),
    ],
)
def test_problem_rejects_out_of_range_cell_indexes(
    cell: TransportCell,
    match: str,
) -> None:
    with pytest.raises(FlowProblemError, match=match):
        _problem((1,), (1,), (cell,))


def test_problem_rejects_duplicate_cell_pair() -> None:
    with pytest.raises(FlowProblemError, match="pairs must be unique"):
        _problem(
            (1,),
            (1,),
            (_cell(0, 0, 1), _cell(0, 0, 2)),
        )


def test_problem_rejects_non_cell_values() -> None:
    with pytest.raises(FlowProblemError, match="TransportCell"):
        _problem(
            (0,),
            (0,),
            cast("tuple[TransportCell, ...]", (object(),)),
        )


def test_cell_rejects_empty_marginal_costs() -> None:
    with pytest.raises(FlowProblemError, match="omit zero-capacity cells"):
        _cell(0, 0)


def test_cell_rejects_unordered_marginal_costs() -> None:
    with pytest.raises(FlowProblemError, match="tuple or list"):
        TransportCell(
            source_index=0,
            destination_index=0,
            marginal_costs=cast("tuple[int, ...]", {1, 2}),
        )


@pytest.mark.parametrize("cost", [-1, True, 1.0])
def test_cell_rejects_invalid_marginal_costs(cost: object) -> None:
    with pytest.raises(FlowProblemError, match="marginal cost"):
        _cell(0, 0, cast("int", cost))


def test_cell_rejects_decreasing_marginal_costs() -> None:
    with pytest.raises(FlowProblemError, match="nondecreasing"):
        _cell(0, 0, 2, 1)


def test_solver_rejects_non_transport_problem() -> None:
    with pytest.raises(FlowProblemError, match="TransportProblem"):
        solve_separable_transport(cast("TransportProblem", object()))


@pytest.mark.parametrize(
    "problem",
    [
        _problem((2,), (2,), (_cell(0, 0, 1),)),
        _problem((2,), (1, 1), (_cell(0, 0, 1, 2),)),
    ],
    ids=["local-source-capacity", "local-destination-capacity"],
)
def test_local_capacity_insufficiency_is_valid_but_infeasible(
    problem: TransportProblem,
) -> None:
    with pytest.raises(InfeasibleTransportError):
        solve_separable_transport(problem)


def test_global_connectivity_infeasibility_raises_typed_error() -> None:
    problem = _problem(
        (1, 1),
        (1, 1),
        (
            _cell(0, 0, 1, 2),
            _cell(1, 0, 1, 2),
        ),
    )

    with pytest.raises(InfeasibleTransportError):
        solve_separable_transport(problem)
