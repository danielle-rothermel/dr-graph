from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

from dr_graph.flow import (
    ArcFlow,
    ArcId,
    FlowArc,
    FlowProblem,
    NodeId,
    solve_min_cost_flow,
)


def _arc(
    arc_id: str,
    source: str,
    target: str,
    capacity: int = 1,
    unit_cost: int = 0,
) -> FlowArc:
    return FlowArc(
        ArcId(arc_id),
        NodeId(source),
        NodeId(target),
        capacity,
        unit_cost,
    )


def test_equal_cost_paths_use_node_declaration_rank() -> None:
    problem = FlowProblem(
        nodes=(NodeId("s"), NodeId("a"), NodeId("b"), NodeId("t")),
        arcs=(
            _arc("s-b", "s", "b"),
            _arc("s-a", "s", "a"),
            _arc("b-t", "b", "t"),
            _arc("a-t", "a", "t"),
        ),
        source=NodeId("s"),
        sink=NodeId("t"),
        required_flow=1,
    )

    result = solve_min_cost_flow(problem)

    assert result.arc_flows == (
        ArcFlow(ArcId("s-b"), 0),
        ArcFlow(ArcId("s-a"), 1),
        ArcFlow(ArcId("b-t"), 0),
        ArcFlow(ArcId("a-t"), 1),
    )


def test_equal_parallel_arcs_use_arc_declaration_order() -> None:
    problem = FlowProblem(
        nodes=(NodeId("s"), NodeId("t")),
        arcs=(
            _arc("declared-first", "s", "t"),
            _arc("declared-second", "s", "t"),
        ),
        source=NodeId("s"),
        sink=NodeId("t"),
        required_flow=1,
    )

    result = solve_min_cost_flow(problem)

    assert result.arc_flows == (
        ArcFlow(ArcId("declared-first"), 1),
        ArcFlow(ArcId("declared-second"), 0),
    )


def test_output_is_stable_across_python_hash_seeds() -> None:
    script = textwrap.dedent(
        """
        import json
        from dr_graph.flow import ArcId, FlowArc, FlowProblem, NodeId
        from dr_graph.flow import solve_min_cost_flow

        def arc(arc_id, source, target):
            return FlowArc(
                ArcId(arc_id), NodeId(source), NodeId(target), 1, 0
            )

        problem = FlowProblem(
            nodes=(NodeId("s"), NodeId("a"), NodeId("b"), NodeId("t")),
            arcs=(
                arc("s-b", "s", "b"),
                arc("s-a", "s", "a"),
                arc("b-t", "b", "t"),
                arc("a-t", "a", "t"),
            ),
            source=NodeId("s"),
            sink=NodeId("t"),
            required_flow=1,
        )
        result = solve_min_cost_flow(problem)
        print(json.dumps([
            [arc_flow.arc_id, arc_flow.flow]
            for arc_flow in result.arc_flows
        ]))
        """
    )

    outputs = []
    for seed in ("0", "1", "17", "8675309", "random"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            env=environment,
            text=True,
        )
        outputs.append(json.loads(completed.stdout))

    assert all(output == outputs[0] for output in outputs)
    assert outputs[0] == [
        ["s-b", 0],
        ["s-a", 1],
        ["b-t", 0],
        ["a-t", 1],
    ]
