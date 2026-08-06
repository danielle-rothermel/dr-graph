from __future__ import annotations

import itertools

import pytest

from dr_graph.flow import (
    ArcId,
    FlowArc,
    FlowProblem,
    InfeasibleFlowError,
    NodeId,
    solve_min_cost_flow,
)


def _minimum_cost_by_enumeration(
    arcs: tuple[FlowArc, ...],
    required_flow: int,
) -> int | None:
    minimum: int | None = None
    for flows in itertools.product(
        *(range(arc.capacity + 1) for arc in arcs)
    ):
        balances = {NodeId("s"): 0, NodeId("a"): 0, NodeId("t"): 0}
        for arc, flow in zip(arcs, flows, strict=True):
            balances[arc.source] += flow
            balances[arc.target] -= flow
        if balances != {
            NodeId("s"): required_flow,
            NodeId("a"): 0,
            NodeId("t"): -required_flow,
        }:
            continue
        cost = sum(
            flow * arc.unit_cost
            for arc, flow in zip(arcs, flows, strict=True)
        )
        minimum = cost if minimum is None else min(minimum, cost)
    return minimum


def test_all_small_parallel_and_two_hop_networks_match_brute_force() -> None:
    endpoints = (
        ("s", "a"),
        ("a", "t"),
        ("s", "t"),
        ("s", "t"),
    )
    for capacities in itertools.product(range(2), repeat=len(endpoints)):
        for costs in itertools.product(range(3), repeat=len(endpoints)):
            arcs = tuple(
                FlowArc(
                    arc_id=ArcId(f"arc-{index}"),
                    source=NodeId(source),
                    target=NodeId(target),
                    capacity=capacity,
                    unit_cost=cost,
                )
                for index, ((source, target), capacity, cost) in enumerate(
                    zip(endpoints, capacities, costs, strict=True)
                )
            )
            for required_flow in range(3):
                problem = FlowProblem(
                    nodes=(NodeId("s"), NodeId("a"), NodeId("t")),
                    arcs=arcs,
                    source=NodeId("s"),
                    sink=NodeId("t"),
                    required_flow=required_flow,
                )
                expected_cost = _minimum_cost_by_enumeration(
                    arcs,
                    required_flow,
                )

                if expected_cost is None:
                    with pytest.raises(InfeasibleFlowError):
                        solve_min_cost_flow(problem)
                else:
                    result = solve_min_cost_flow(problem)
                    assert result.sent_flow == required_flow
                    assert result.total_cost == expected_cost
