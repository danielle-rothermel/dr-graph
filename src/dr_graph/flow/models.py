from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from dr_graph.flow.errors import FlowProblemError

NodeId = NewType("NodeId", str)
ArcId = NewType("ArcId", str)


def _snapshot_ordered_collection[T](
    value: tuple[T, ...] | list[T],
    *,
    name: str,
) -> tuple[T, ...]:
    if type(value) not in (tuple, list):
        raise FlowProblemError(f"{name} must be a tuple or list")
    return tuple(value)


def _validate_identity(value: object, *, name: str) -> None:
    if type(value) is not str:
        raise FlowProblemError(f"{name} must be an exact string")
    if not value:
        raise FlowProblemError(f"{name} must be nonempty")


def _validate_nonnegative_int(value: object, *, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FlowProblemError(f"{name} must be an integer")
    if value < 0:
        raise FlowProblemError(f"{name} must be nonnegative")


@dataclass(frozen=True, slots=True)
class FlowArc:
    """One directed, capacitated, nonnegative-cost arc."""

    arc_id: ArcId
    source: NodeId
    target: NodeId
    capacity: int
    unit_cost: int

    def __post_init__(self) -> None:
        _validate_identity(self.arc_id, name="arc_id")
        _validate_identity(self.source, name="arc source")
        _validate_identity(self.target, name="arc target")
        _validate_nonnegative_int(self.capacity, name="arc capacity")
        _validate_nonnegative_int(self.unit_cost, name="arc unit_cost")


@dataclass(frozen=True, slots=True)
class FlowProblem:
    """An exact single-source, single-sink min-cost flow problem."""

    nodes: tuple[NodeId, ...]
    arcs: tuple[FlowArc, ...]
    source: NodeId
    sink: NodeId
    required_flow: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "nodes",
            _snapshot_ordered_collection(self.nodes, name="nodes"),
        )
        object.__setattr__(
            self,
            "arcs",
            _snapshot_ordered_collection(self.arcs, name="arcs"),
        )
        _validate_problem(self)


def _validate_problem(problem: FlowProblem) -> None:
    if not problem.nodes:
        raise FlowProblemError("flow problem must declare at least one node")

    for node in problem.nodes:
        _validate_identity(node, name="node id")
    if len(set(problem.nodes)) != len(problem.nodes):
        raise FlowProblemError("node ids must be unique")

    _validate_identity(problem.source, name="source")
    _validate_identity(problem.sink, name="sink")
    if problem.source == problem.sink:
        raise FlowProblemError("source and sink must be distinct")

    declared_nodes = set(problem.nodes)
    if problem.source not in declared_nodes:
        raise FlowProblemError("source must be a declared node")
    if problem.sink not in declared_nodes:
        raise FlowProblemError("sink must be a declared node")

    _validate_nonnegative_int(
        problem.required_flow,
        name="required_flow",
    )

    arc_ids: set[ArcId] = set()
    for arc in problem.arcs:
        if not isinstance(arc, FlowArc):
            raise FlowProblemError("arcs must contain FlowArc values")
        if arc.arc_id in arc_ids:
            raise FlowProblemError("arc ids must be unique")
        arc_ids.add(arc.arc_id)
        if arc.source not in declared_nodes:
            raise FlowProblemError(
                f"arc {arc.arc_id!r} source must be a declared node"
            )
        if arc.target not in declared_nodes:
            raise FlowProblemError(
                f"arc {arc.arc_id!r} target must be a declared node"
            )


@dataclass(frozen=True, slots=True)
class ArcFlow:
    arc_id: ArcId
    flow: int


@dataclass(frozen=True, slots=True)
class FlowResult:
    """An exact min-cost result in the problem's arc declaration order."""

    sent_flow: int
    total_cost: int
    arc_flows: tuple[ArcFlow, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "arc_flows",
            _snapshot_ordered_collection(
                self.arc_flows,
                name="arc_flows",
            ),
        )
