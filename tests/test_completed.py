"""Completed-nodes resume hook: skip prior work, reuse its outputs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from dr_graph import (
    CompletedNodeError,
    GraphRunStatus,
    NodeOutcomeStatus,
    NodeOutput,
    NodeSpec,
    execute_graph,
    graph,
    node,
)


def _encdec():
    return graph(
        [
            node(
                "encoder",
                op="llm_call",
                bindings={"prompt": "task.prompt"},
                output_field="description",
            ),
            node(
                "decoder",
                op="llm_call",
                bindings={"description": "encoder.description"},
                output_field="code",
            ),
        ],
        terminal="decoder",
    )


def test_completed_nodes_are_skipped_and_feed_bindings() -> None:
    invoked: list[str] = []

    def run_node(
        node_spec: NodeSpec,
        inputs: Mapping[str, Any],
    ) -> dict[str, Any]:
        invoked.append(node_spec.id)
        return {
            "values": {
                node_spec.config.output_field: f"new({inputs['description']})"
            }
        }

    result = execute_graph(
        graph=_encdec(),
        inputs={"prompt": "unused because encoder is completed"},
        run_node=run_node,
        completed={
            "encoder": {"values": {"description": "prior description"}},
        },
    )

    assert invoked == ["decoder"]
    assert result.status is GraphRunStatus.SUCCESS
    assert result.terminal_output == "new(prior description)"
    assert result.outcomes["encoder"].status is NodeOutcomeStatus.SUCCESS
    assert result.execution_order == ("encoder", "decoder")


def test_completed_accepts_node_output_instances() -> None:
    result = execute_graph(
        graph=_encdec(),
        inputs={},
        run_node=lambda node_spec, inputs: {
            "values": {node_spec.config.output_field: inputs["description"]}
        },
        completed={
            "encoder": NodeOutput(values={"description": "prior"}),
        },
    )
    assert result.status is GraphRunStatus.SUCCESS
    assert result.terminal_output == "prior"


def test_fully_completed_graph_runs_without_callback_calls() -> None:
    def run_node(
        node_spec: NodeSpec,
        inputs: Mapping[str, Any],
    ) -> dict[str, Any]:
        raise AssertionError("run_node must not be called")

    result = execute_graph(
        graph=_encdec(),
        inputs={},
        run_node=run_node,
        completed={
            "encoder": {"values": {"description": "d"}},
            "decoder": {"values": {"code": "c"}},
        },
    )
    assert result.status is GraphRunStatus.SUCCESS
    assert result.terminal_output == "c"


def test_completed_unknown_node_rejected_before_execution() -> None:
    invoked: list[str] = []

    def run_node(
        node_spec: NodeSpec,
        inputs: Mapping[str, Any],
    ) -> dict[str, Any]:
        invoked.append(node_spec.id)
        return {"values": {node_spec.config.output_field: "x"}}

    with pytest.raises(CompletedNodeError, match="not in the graph"):
        execute_graph(
            graph=_encdec(),
            inputs={"prompt": "p"},
            run_node=run_node,
            completed={"missing": {"values": {"output": "x"}}},
        )
    assert invoked == []


def test_completed_output_missing_declared_field_rejected() -> None:
    with pytest.raises(CompletedNodeError, match="missing field"):
        execute_graph(
            graph=_encdec(),
            inputs={"prompt": "p"},
            run_node=lambda node_spec, inputs: {"values": {}},
            completed={"encoder": {"values": {"wrong_field": "d"}}},
        )


def test_completed_output_invalid_shape_rejected() -> None:
    with pytest.raises(CompletedNodeError, match="invalid"):
        execute_graph(
            graph=_encdec(),
            inputs={"prompt": "p"},
            run_node=lambda node_spec, inputs: {"values": {}},
            completed={"encoder": {"nonsense": True}},
        )
