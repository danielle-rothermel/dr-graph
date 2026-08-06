from __future__ import annotations

from dataclasses import dataclass

from dr_graph.flow.errors import FlowProblemError
from dr_graph.flow.models import _snapshot_ordered_collection


def _validate_nonnegative_int(value: object, *, name: str) -> None:
    if type(value) is not int:
        raise FlowProblemError(f"{name} must be an exact integer")
    if value < 0:
        raise FlowProblemError(f"{name} must be nonnegative")


@dataclass(frozen=True, slots=True)
class TransportCell:
    """One route with nonnegative, nondecreasing marginal costs.

    Omit a cell from a problem to represent an unavailable or zero-capacity
    route. Each marginal cost is one unit of available capacity.
    """

    source_index: int
    destination_index: int
    marginal_costs: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "marginal_costs",
            _snapshot_ordered_collection(
                self.marginal_costs,
                name="cell marginal_costs",
            ),
        )
        _validate_nonnegative_int(
            self.source_index,
            name="cell source_index",
        )
        _validate_nonnegative_int(
            self.destination_index,
            name="cell destination_index",
        )
        if not self.marginal_costs:
            raise FlowProblemError(
                "cell marginal_costs must be nonempty; omit zero-capacity "
                "cells"
            )
        previous_cost: int | None = None
        for cost in self.marginal_costs:
            _validate_nonnegative_int(cost, name="cell marginal cost")
            if previous_cost is not None and cost < previous_cost:
                raise FlowProblemError(
                    "cell marginal_costs must be nondecreasing"
                )
            previous_cost = cost


@dataclass(frozen=True, slots=True)
class TransportProblem:
    """A balanced separable transportation problem.

    Missing cells are unavailable. Available cells always have at least one
    marginal-cost entry, with one unit of capacity per entry.
    """

    supplies: tuple[int, ...]
    demands: tuple[int, ...]
    cells: tuple[TransportCell, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "supplies",
            _snapshot_ordered_collection(self.supplies, name="supplies"),
        )
        object.__setattr__(
            self,
            "demands",
            _snapshot_ordered_collection(self.demands, name="demands"),
        )
        object.__setattr__(
            self,
            "cells",
            _snapshot_ordered_collection(self.cells, name="cells"),
        )
        _validate_transport_problem(self)


@dataclass(frozen=True, slots=True)
class TransportSolution:
    """A minimum-cost allocation in source and destination index order."""

    allocations: tuple[tuple[int, ...], ...]
    total_flow: int
    total_cost: int

    def __post_init__(self) -> None:
        rows = _snapshot_ordered_collection(
            self.allocations,
            name="allocations",
        )
        object.__setattr__(
            self,
            "allocations",
            tuple(
                _snapshot_ordered_collection(row, name="allocation row")
                for row in rows
            ),
        )


def _validate_transport_problem(problem: TransportProblem) -> None:
    for supply in problem.supplies:
        _validate_nonnegative_int(supply, name="supply")
    for demand in problem.demands:
        _validate_nonnegative_int(demand, name="demand")

    if sum(problem.supplies) != sum(problem.demands):
        raise FlowProblemError("total supply must equal total demand")

    cell_pairs: set[tuple[int, int]] = set()
    for cell in problem.cells:
        if not isinstance(cell, TransportCell):
            raise FlowProblemError("cells must contain TransportCell values")
        if cell.source_index >= len(problem.supplies):
            raise FlowProblemError("cell source_index is out of range")
        if cell.destination_index >= len(problem.demands):
            raise FlowProblemError("cell destination_index is out of range")
        pair = (cell.source_index, cell.destination_index)
        if pair in cell_pairs:
            raise FlowProblemError(
                "source/destination cell pairs must be unique"
            )
        cell_pairs.add(pair)
