from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

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
    return FlowProblem(nodes, arcs, source, sink, required_flow)


def test_problem_snapshots_caller_owned_collections() -> None:
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("nodes", "st"),
        ("nodes", {NodeId("s"), NodeId("t")}),
        ("arcs", set()),
    ],
)
def test_problem_rejects_scalar_and_unordered_collections(
    field: str,
    value: object,
) -> None:
    nodes = cast("tuple[NodeId, ...]", value) if field == "nodes" else ()
    arcs = cast("tuple[FlowArc, ...]", value) if field == "arcs" else ()

    with pytest.raises(FlowProblemError):
        FlowProblem(nodes, arcs, NodeId("s"), NodeId("t"), 0)


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


def test_result_snapshots_caller_owned_arc_flows() -> None:
    caller_flows = [ArcFlow(ArcId("a"), 0)]
    result = FlowResult(0, 0, cast("tuple[ArcFlow, ...]", caller_flows))
    caller_flows.clear()

    assert result.arc_flows == (ArcFlow(ArcId("a"), 0),)


@pytest.mark.parametrize(
    ("nodes", "source", "sink"),
    [
        ((), "s", "t"),
        (("s", "s", "t"), "s", "t"),
        (("s", "t"), "s", "s"),
        (("s", "t"), "missing", "t"),
        (("s", "t"), "s", "missing"),
        (("", "t"), "", "t"),
    ],
)
def test_problem_rejects_invalid_node_contracts(
    nodes: tuple[str, ...],
    source: str,
    sink: str,
) -> None:
    with pytest.raises(FlowProblemError):
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
    with pytest.raises(FlowProblemError):
        _problem(nodes=(cast("NodeId", node), NodeId("t")))


@pytest.mark.parametrize("required_flow", [-1, True, 1.0, "1"])
def test_problem_rejects_invalid_required_flow(
    required_flow: object,
) -> None:
    with pytest.raises(FlowProblemError):
        _problem(required_flow=cast("int", required_flow))


@pytest.mark.parametrize(
    ("capacity", "unit_cost"),
    [(-1, 0), (True, 0), (1.0, 0), (1, -1), (1, True), (1, 1.0)],
)
def test_arc_rejects_invalid_numeric_contracts(
    capacity: object,
    unit_cost: object,
) -> None:
    with pytest.raises(FlowProblemError):
        _arc(
            "a",
            "s",
            "t",
            capacity=cast("int", capacity),
            unit_cost=cast("int", unit_cost),
        )


@pytest.mark.parametrize(
    ("arc_id", "source", "target"),
    [("", "s", "t"), ("a", "", "t"), ("a", "s", "")],
)
def test_arc_rejects_empty_identities(
    arc_id: str,
    source: str,
    target: str,
) -> None:
    with pytest.raises(FlowProblemError):
        _arc(arc_id, source, target)


@pytest.mark.parametrize("identity", [1, True, _StringSubclass("a")])
def test_arc_rejects_identities_that_are_not_exact_strings(
    identity: object,
) -> None:
    with pytest.raises(FlowProblemError):
        FlowArc(
            cast("ArcId", identity),
            NodeId("s"),
            NodeId("t"),
            1,
            0,
        )


def test_problem_rejects_duplicate_arc_ids() -> None:
    with pytest.raises(FlowProblemError):
        _problem(arcs=(_arc("a", "s", "t"), _arc("a", "s", "t")))


@pytest.mark.parametrize(
    "arc",
    [_arc("a", "missing", "t"), _arc("a", "s", "missing")],
)
def test_problem_rejects_undeclared_arc_endpoints(arc: FlowArc) -> None:
    with pytest.raises(FlowProblemError):
        _problem(arcs=(arc,))
