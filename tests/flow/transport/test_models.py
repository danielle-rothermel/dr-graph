from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from dr_graph.flow.transport import (
    FlowProblemError,
    TransportCell,
    TransportProblem,
    TransportSolution,
)
from tests.flow.transport.support import cell, problem


def _assign_attribute(value: object, name: str, replacement: object) -> None:
    setattr(value, name, replacement)


def test_problem_snapshots_caller_owned_collections() -> None:
    supplies = [1]
    demands = [1]
    cells = [cell(0, 0, 2)]
    transport_problem = TransportProblem(
        cast("tuple[int, ...]", supplies),
        cast("tuple[int, ...]", demands),
        cast("tuple[TransportCell, ...]", cells),
    )
    supplies.clear()
    demands.clear()
    cells.clear()

    assert transport_problem == problem((1,), (1,), (cell(0, 0, 2),))


@pytest.mark.parametrize(
    ("field", "value"),
    [("supplies", {1}), ("demands", {1}), ("cells", set())],
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
        else (cell(0, 0, 1),)
    )

    with pytest.raises(FlowProblemError):
        problem(supplies, demands, cells)


def test_solution_snapshots_caller_owned_allocations() -> None:
    allocations = [[1]]
    solution = TransportSolution(
        cast("tuple[tuple[int, ...], ...]", allocations),
        1,
        2,
    )
    allocations[0].clear()
    allocations.clear()

    assert solution.allocations == ((1,),)


def test_transport_values_are_frozen_and_slotted() -> None:
    transport_cell = cell(0, 0, 1)
    transport_problem = problem((1,), (1,), (transport_cell,))
    solution = TransportSolution(((1,),), 1, 1)

    with pytest.raises(FrozenInstanceError):
        _assign_attribute(transport_cell, "source_index", 1)
    with pytest.raises(FrozenInstanceError):
        _assign_attribute(transport_problem, "supplies", (2,))
    with pytest.raises(FrozenInstanceError):
        _assign_attribute(solution, "total_flow", 2)

    assert not hasattr(transport_cell, "__dict__")
    assert not hasattr(transport_problem, "__dict__")
    assert not hasattr(solution, "__dict__")


@pytest.mark.parametrize(
    ("supplies", "demands"),
    [
        ((-1,), (0,)),
        ((True,), (0,)),
        ((1.0,), (0,)),
        ((0,), (-1,)),
        ((0,), (False,)),
        ((0,), (1.0,)),
    ],
)
def test_problem_rejects_invalid_supply_and_demand_values(
    supplies: tuple[object, ...],
    demands: tuple[object, ...],
) -> None:
    with pytest.raises(FlowProblemError):
        problem(
            cast("tuple[int, ...]", supplies),
            cast("tuple[int, ...]", demands),
            (),
        )


def test_problem_rejects_unbalanced_totals() -> None:
    with pytest.raises(FlowProblemError):
        problem((1,), (0,), ())


@pytest.mark.parametrize(
    ("source_index", "destination_index"),
    [(-1, 0), (True, 0), (0.0, 0), (0, -1), (0, False), (0, 0.0)],
)
def test_cell_rejects_invalid_indexes(
    source_index: object,
    destination_index: object,
) -> None:
    with pytest.raises(FlowProblemError):
        cell(
            cast("int", source_index),
            cast("int", destination_index),
            1,
        )


@pytest.mark.parametrize(
    "transport_cell",
    [cell(1, 0, 1), cell(0, 1, 1)],
)
def test_problem_rejects_out_of_range_cell_indexes(
    transport_cell: TransportCell,
) -> None:
    with pytest.raises(FlowProblemError):
        problem((1,), (1,), (transport_cell,))


def test_problem_rejects_duplicate_cell_pair() -> None:
    with pytest.raises(FlowProblemError):
        problem((1,), (1,), (cell(0, 0, 1), cell(0, 0, 2)))


def test_problem_rejects_non_cell_values() -> None:
    with pytest.raises(FlowProblemError):
        problem(
            (0,),
            (0,),
            cast("tuple[TransportCell, ...]", (object(),)),
        )


def test_cell_rejects_empty_marginal_costs() -> None:
    with pytest.raises(FlowProblemError):
        cell(0, 0)


def test_cell_rejects_unordered_marginal_costs() -> None:
    with pytest.raises(FlowProblemError):
        TransportCell(
            source_index=0,
            destination_index=0,
            marginal_costs=cast("tuple[int, ...]", {1, 2}),
        )


@pytest.mark.parametrize("cost", [-1, True, 1.0])
def test_cell_rejects_invalid_marginal_costs(cost: object) -> None:
    with pytest.raises(FlowProblemError):
        cell(0, 0, cast("int", cost))


def test_cell_rejects_decreasing_marginal_costs() -> None:
    with pytest.raises(FlowProblemError):
        cell(0, 0, 2, 1)
