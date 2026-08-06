from __future__ import annotations

from dataclasses import dataclass

from dr_graph.flow.errors import (
    FlowProblemError,
    InfeasibleFlowError,
    InfeasibleTransportError,
)
from dr_graph.flow.models import ArcId, FlowArc, FlowProblem, NodeId
from dr_graph.flow.solver import solve_min_cost_flow


def _validate_nonnegative_int(value: object, *, name: str) -> None:
    if type(value) is not int:
        raise FlowProblemError(f"{name} must be an exact integer")
    if value < 0:
        raise FlowProblemError(f"{name} must be nonnegative")


@dataclass(frozen=True, slots=True)
class TransportCell:
    """One available source-to-destination route with convex unit costs.

    Omit a cell from a problem to represent an unavailable or zero-capacity
    route. Each marginal cost is one unit of available capacity.
    """

    source_index: int
    destination_index: int
    marginal_costs: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "marginal_costs", tuple(self.marginal_costs))
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
        object.__setattr__(self, "supplies", tuple(self.supplies))
        object.__setattr__(self, "demands", tuple(self.demands))
        object.__setattr__(self, "cells", tuple(self.cells))
        _validate_transport_problem(self)


@dataclass(frozen=True, slots=True)
class TransportSolution:
    """A minimum-cost allocation in source and destination index order."""

    allocations: tuple[tuple[int, ...], ...]
    total_flow: int
    total_cost: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "allocations",
            tuple(tuple(row) for row in self.allocations),
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


def solve_separable_transport(
    problem: TransportProblem,
) -> TransportSolution:
    """Return the exact minimum-cost allocation for a balanced problem."""
    if not isinstance(problem, TransportProblem):
        raise FlowProblemError("problem must be a TransportProblem")

    required_flow = sum(problem.supplies)
    empty_allocations = tuple(
        tuple(0 for _demand in problem.demands) for _supply in problem.supplies
    )
    if required_flow == 0:
        return TransportSolution(
            allocations=empty_allocations,
            total_flow=0,
            total_cost=0,
        )

    flow_problem, cell_arc_indexes = _translate_problem(problem)
    try:
        flow_result = solve_min_cost_flow(flow_problem)
    except InfeasibleFlowError as error:
        raise InfeasibleTransportError(
            "transport network cannot satisfy every supply and demand"
        ) from error

    allocations = [list(row) for row in empty_allocations]
    for cell, arc_indexes in zip(
        problem.cells,
        cell_arc_indexes,
        strict=True,
    ):
        allocations[cell.source_index][cell.destination_index] = sum(
            flow_result.arc_flows[arc_index].flow for arc_index in arc_indexes
        )

    return TransportSolution(
        allocations=tuple(tuple(row) for row in allocations),
        total_flow=flow_result.sent_flow,
        total_cost=flow_result.total_cost,
    )


def _translate_problem(
    problem: TransportProblem,
) -> tuple[FlowProblem, tuple[tuple[int, ...], ...]]:
    super_source = NodeId("transport:super-source")
    source_nodes = tuple(
        NodeId(f"transport:source:{index}")
        for index in range(len(problem.supplies))
    )
    destination_nodes = tuple(
        NodeId(f"transport:destination:{index}")
        for index in range(len(problem.demands))
    )
    super_sink = NodeId("transport:super-sink")

    arcs: list[FlowArc] = []
    for source_index, supply in enumerate(problem.supplies):
        arcs.append(
            FlowArc(
                arc_id=ArcId(f"transport:supply:{source_index}"),
                source=super_source,
                target=source_nodes[source_index],
                capacity=supply,
                unit_cost=0,
            )
        )

    cell_arc_indexes: list[tuple[int, ...]] = []
    for cell_index, cell in enumerate(problem.cells):
        marginal_arc_indexes: list[int] = []
        for marginal_index, marginal_cost in enumerate(cell.marginal_costs):
            marginal_arc_indexes.append(len(arcs))
            arcs.append(
                FlowArc(
                    arc_id=ArcId(
                        f"transport:cell:{cell_index}:unit:{marginal_index}"
                    ),
                    source=source_nodes[cell.source_index],
                    target=destination_nodes[cell.destination_index],
                    capacity=1,
                    unit_cost=marginal_cost,
                )
            )
        cell_arc_indexes.append(tuple(marginal_arc_indexes))

    for destination_index, demand in enumerate(problem.demands):
        arcs.append(
            FlowArc(
                arc_id=ArcId(f"transport:demand:{destination_index}"),
                source=destination_nodes[destination_index],
                target=super_sink,
                capacity=demand,
                unit_cost=0,
            )
        )

    return (
        FlowProblem(
            nodes=(
                super_source,
                *source_nodes,
                *destination_nodes,
                super_sink,
            ),
            arcs=tuple(arcs),
            source=super_source,
            sink=super_sink,
            required_flow=sum(problem.supplies),
        ),
        tuple(cell_arc_indexes),
    )
