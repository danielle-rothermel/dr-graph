from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

import dr_graph
from dr_graph.flow import (
    ArcFlow,
    ArcId,
    FlowArc,
    FlowProblem,
    FlowProblemError,
    FlowResult,
    NodeId,
    solve_min_cost_flow,
)

_SOURCE = NodeId("s")
_SINK = NodeId("t")


def _assign_attribute(value: object, name: str, replacement: object) -> None:
    setattr(value, name, replacement)


def test_flow_api_is_not_reexported_from_top_level_package() -> None:
    assert not hasattr(dr_graph, "FlowProblem")
    assert not hasattr(dr_graph, "solve_min_cost_flow")


def _arc(
    arc_id: str,
    source: str,
    target: str,
    capacity: int = 1,
    unit_cost: int = 0,
) -> FlowArc:
    return FlowArc(
        arc_id=ArcId(arc_id),
        source=NodeId(source),
        target=NodeId(target),
        capacity=capacity,
        unit_cost=unit_cost,
    )


def _problem(
    *,
    nodes: tuple[NodeId, ...] = (_SOURCE, _SINK),
    arcs: tuple[FlowArc, ...] = (),
    source: NodeId = _SOURCE,
    sink: NodeId = _SINK,
    required_flow: int = 0,
) -> FlowProblem:
    return FlowProblem(
        nodes=nodes,
        arcs=arcs,
        source=source,
        sink=sink,
        required_flow=required_flow,
    )


def test_problem_copies_caller_owned_collections_to_tuples() -> None:
    caller_nodes = [NodeId("s"), NodeId("t")]
    caller_arcs = [_arc("direct", "s", "t")]

    problem = FlowProblem(
        nodes=cast("tuple[NodeId, ...]", caller_nodes),
        arcs=cast("tuple[FlowArc, ...]", caller_arcs),
        source=NodeId("s"),
        sink=NodeId("t"),
        required_flow=1,
    )
    caller_nodes.append(NodeId("later"))
    caller_arcs.clear()

    assert problem.nodes == (NodeId("s"), NodeId("t"))
    assert problem.arcs == (_arc("direct", "s", "t"),)
    assert isinstance(problem.nodes, tuple)
    assert isinstance(problem.arcs, tuple)


def test_public_values_are_frozen_and_slotted() -> None:
    problem = _problem()
    result = solve_min_cost_flow(problem)
    arc = _arc("a", "s", "t")
    arc_flow = ArcFlow(ArcId("a"), 0)

    with pytest.raises(FrozenInstanceError):
        _assign_attribute(problem, "required_flow", 1)
    with pytest.raises(FrozenInstanceError):
        _assign_attribute(result, "sent_flow", 1)
    with pytest.raises(FrozenInstanceError):
        _assign_attribute(arc, "capacity", 2)
    with pytest.raises(FrozenInstanceError):
        _assign_attribute(arc_flow, "flow", 1)

    assert not hasattr(problem, "__dict__")
    assert not hasattr(result, "__dict__")
    assert not hasattr(arc, "__dict__")
    assert not hasattr(arc_flow, "__dict__")
    assert isinstance(result.arc_flows, tuple)


def test_result_copies_caller_owned_collection_to_a_tuple() -> None:
    caller_flows = [ArcFlow(ArcId("a"), 0)]

    result = FlowResult(
        sent_flow=0,
        total_cost=0,
        arc_flows=cast("tuple[ArcFlow, ...]", caller_flows),
    )
    caller_flows.clear()

    assert result.arc_flows == (ArcFlow(ArcId("a"), 0),)


@pytest.mark.parametrize(
    ("nodes", "source", "sink", "match"),
    [
        ((), "s", "t", "at least one node"),
        (("s", "s", "t"), "s", "t", "node ids must be unique"),
        (("s", "t"), "s", "s", "must be distinct"),
        (("s", "t"), "missing", "t", "source must be a declared"),
        (("s", "t"), "s", "missing", "sink must be a declared"),
        (("", "t"), "", "t", "node id must be nonempty"),
    ],
)
def test_problem_rejects_invalid_node_contracts(
    nodes: tuple[str, ...],
    source: str,
    sink: str,
    match: str,
) -> None:
    with pytest.raises(FlowProblemError, match=match):
        _problem(
            nodes=tuple(NodeId(node) for node in nodes),
            source=NodeId(source),
            sink=NodeId(sink),
        )


class _StringSubclass(str):
    __slots__ = ()


@pytest.mark.parametrize("node", [1, True, _StringSubclass("s")])
def test_problem_rejects_node_ids_that_are_not_exact_strings(
    node: object,
) -> None:
    with pytest.raises(FlowProblemError, match="exact string"):
        _problem(nodes=(cast("NodeId", node), NodeId("t")))


@pytest.mark.parametrize("required_flow", [-1, True, 1.0, "1"])
def test_problem_rejects_invalid_required_flow(
    required_flow: object,
) -> None:
    with pytest.raises(FlowProblemError, match="required_flow"):
        _problem(required_flow=cast("int", required_flow))


@pytest.mark.parametrize(
    ("capacity", "unit_cost", "match"),
    [
        (-1, 0, "capacity"),
        (True, 0, "capacity"),
        (1.0, 0, "capacity"),
        (1, -1, "unit_cost"),
        (1, True, "unit_cost"),
        (1, 1.0, "unit_cost"),
    ],
)
def test_arc_rejects_invalid_numeric_contracts(
    capacity: object,
    unit_cost: object,
    match: str,
) -> None:
    with pytest.raises(FlowProblemError, match=match):
        _arc(
            "a",
            "s",
            "t",
            capacity=cast("int", capacity),
            unit_cost=cast("int", unit_cost),
        )


@pytest.mark.parametrize(
    ("arc_id", "source", "target", "match"),
    [
        ("", "s", "t", "arc_id must be nonempty"),
        ("a", "", "t", "arc source must be nonempty"),
        ("a", "s", "", "arc target must be nonempty"),
    ],
)
def test_arc_rejects_empty_identities(
    arc_id: str,
    source: str,
    target: str,
    match: str,
) -> None:
    with pytest.raises(FlowProblemError, match=match):
        _arc(arc_id, source, target)


@pytest.mark.parametrize("identity", [1, True, _StringSubclass("a")])
def test_arc_rejects_identities_that_are_not_exact_strings(
    identity: object,
) -> None:
    with pytest.raises(FlowProblemError, match="exact string"):
        FlowArc(
            arc_id=cast("ArcId", identity),
            source=NodeId("s"),
            target=NodeId("t"),
            capacity=1,
            unit_cost=0,
        )


def test_problem_rejects_duplicate_arc_ids() -> None:
    with pytest.raises(FlowProblemError, match="arc ids must be unique"):
        _problem(arcs=(_arc("a", "s", "t"), _arc("a", "s", "t")))


@pytest.mark.parametrize(
    ("arc", "match"),
    [
        (_arc("a", "missing", "t"), "source must be a declared"),
        (_arc("a", "s", "missing"), "target must be a declared"),
    ],
)
def test_problem_rejects_undeclared_arc_endpoints(
    arc: FlowArc,
    match: str,
) -> None:
    with pytest.raises(FlowProblemError, match=match):
        _problem(arcs=(arc,))


def test_solver_rejects_non_problem_input() -> None:
    with pytest.raises(FlowProblemError, match="must be a FlowProblem"):
        solve_min_cost_flow(cast("FlowProblem", object()))
