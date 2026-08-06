from __future__ import annotations

from typing import cast

import pytest

from dr_graph.flow import (
    ArcFlow,
    ArcId,
    FlowArc,
    FlowProblem,
    FlowProblemError,
    InfeasibleFlowError,
    NodeId,
    solve_min_cost_flow,
)


def _arc(
    arc_id: str,
    source: str,
    target: str,
    capacity: int,
    unit_cost: int,
) -> FlowArc:
    return FlowArc(
        arc_id=ArcId(arc_id),
        source=NodeId(source),
        target=NodeId(target),
        capacity=capacity,
        unit_cost=unit_cost,
    )


def _problem(
    nodes: tuple[str, ...],
    arcs: tuple[FlowArc, ...],
    required_flow: int,
) -> FlowProblem:
    return FlowProblem(
        nodes=tuple(NodeId(node) for node in nodes),
        arcs=arcs,
        source=NodeId("s"),
        sink=NodeId("t"),
        required_flow=required_flow,
    )


def test_solver_returns_exact_conserved_minimum_cost_flow() -> None:
    problem = _problem(
        ("s", "a", "b", "t"),
        (
            _arc("s-a", "s", "a", 3, 1),
            _arc("a-t", "a", "t", 3, 2),
            _arc("s-b", "s", "b", 2, 0),
            _arc("b-t", "b", "t", 2, 1),
            _arc("a-b", "a", "b", 1, 0),
        ),
        required_flow=4,
    )

    result = solve_min_cost_flow(problem)

    assert result.sent_flow == 4
    assert result.total_cost == 8
    assert result.arc_flows == (
        ArcFlow(ArcId("s-a"), 2),
        ArcFlow(ArcId("a-t"), 2),
        ArcFlow(ArcId("s-b"), 2),
        ArcFlow(ArcId("b-t"), 2),
        ArcFlow(ArcId("a-b"), 0),
    )


def test_zero_required_flow_returns_every_arc_with_zero_flow() -> None:
    problem = _problem(
        ("s", "t"),
        (
            _arc("available", "s", "t", 2, 3),
            _arc("zero-capacity", "s", "t", 0, 0),
        ),
        required_flow=0,
    )

    result = solve_min_cost_flow(problem)

    assert result.sent_flow == 0
    assert result.total_cost == 0
    assert result.arc_flows == (
        ArcFlow(ArcId("available"), 0),
        ArcFlow(ArcId("zero-capacity"), 0),
    )


def test_zero_capacity_arc_is_valid_and_never_used() -> None:
    problem = _problem(
        ("s", "t"),
        (
            _arc("blocked", "s", "t", 0, 0),
            _arc("usable", "s", "t", 1, 4),
        ),
        required_flow=1,
    )

    result = solve_min_cost_flow(problem)

    assert result.total_cost == 4
    assert result.arc_flows == (
        ArcFlow(ArcId("blocked"), 0),
        ArcFlow(ArcId("usable"), 1),
    )


def test_parallel_arcs_are_independently_addressed_by_arc_id() -> None:
    problem = _problem(
        ("s", "t"),
        (
            _arc("cheap", "s", "t", 1, 1),
            _arc("expensive", "s", "t", 2, 3),
        ),
        required_flow=2,
    )

    result = solve_min_cost_flow(problem)

    assert result.total_cost == 4
    assert result.arc_flows == (
        ArcFlow(ArcId("cheap"), 1),
        ArcFlow(ArcId("expensive"), 1),
    )


def test_infeasible_exact_flow_raises_typed_error() -> None:
    problem = _problem(
        ("s", "middle", "t"),
        (
            _arc("start", "s", "middle", 2, 0),
            _arc("finish", "middle", "t", 1, 0),
        ),
        required_flow=2,
    )

    with pytest.raises(InfeasibleFlowError):
        solve_min_cost_flow(problem)


def test_residual_reverse_arc_reroutes_an_earlier_augmentation() -> None:
    problem = _problem(
        ("s", "a", "b", "t"),
        (
            _arc("s-a", "s", "a", 1, 0),
            _arc("s-b", "s", "b", 1, 0),
            _arc("a-b", "a", "b", 1, 0),
            _arc("a-t", "a", "t", 1, 1),
            _arc("b-t", "b", "t", 1, 0),
        ),
        required_flow=2,
    )

    result = solve_min_cost_flow(problem)

    assert result.total_cost == 1
    assert result.arc_flows == (
        ArcFlow(ArcId("s-a"), 1),
        ArcFlow(ArcId("s-b"), 1),
        ArcFlow(ArcId("a-b"), 0),
        ArcFlow(ArcId("a-t"), 1),
        ArcFlow(ArcId("b-t"), 1),
    )


def test_solver_rejects_non_problem_input() -> None:
    with pytest.raises(FlowProblemError):
        solve_min_cost_flow(cast("FlowProblem", object()))
