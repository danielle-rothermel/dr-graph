from __future__ import annotations

import pytest

from dr_graph import GraphConfig
from tests.support import _graph, _node


def test_duplicate_node_id_validation() -> None:
    with pytest.raises(ValueError, match="duplicate node ids"):
        GraphConfig(
            nodes=(_node("same"), _node("same")),
            terminal_node_id="same",
        )


def test_unknown_dependency_validation() -> None:
    with pytest.raises(ValueError, match="points at unknown node"):
        GraphConfig(
            nodes=(
                _node("decoder", input_sources={"description": "encoder"}),
            ),
            terminal_node_id="decoder",
        )


def test_cycle_detection() -> None:
    with pytest.raises(ValueError, match="graph has a cycle"):
        GraphConfig(
            nodes=(
                _node("a", input_sources={"value": "b"}),
                _node("b", input_sources={"value": "a"}),
            ),
            terminal_node_id="a",
        )


def test_empty_graph_validation() -> None:
    with pytest.raises(ValueError, match="graph must have at least one node"):
        GraphConfig(nodes=(), terminal_node_id="missing")


def test_missing_terminal_node_validation() -> None:
    with pytest.raises(
        ValueError,
        match="terminal_node_id 'missing' not in graph",
    ):
        GraphConfig(nodes=(_node("direct"),), terminal_node_id="missing")


def test_second_sink_node_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="more than one terminal/sink node",
    ):
        GraphConfig(
            nodes=(_node("terminal"), _node("bad")),
            terminal_node_id="terminal",
        )


def test_terminal_consumed_by_other_node_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="is consumed by another node and cannot be the sink",
    ):
        GraphConfig(
            nodes=(
                _node("encoder", output_field="description"),
                _node("decoder", input_sources={"description": "encoder"}),
            ),
            terminal_node_id="encoder",
        )


def test_missing_named_upstream_output_field_validation() -> None:
    with pytest.raises(ValueError, match="points at unknown field 'other'"):
        GraphConfig(
            nodes=(
                _node("encoder", output_field="description"),
                _node(
                    "decoder",
                    input_sources={"description": "encoder.other"},
                ),
            ),
            terminal_node_id="decoder",
        )


def test_input_source_round_trips_through_graph_config_json_dump() -> None:
    graph = _graph(
        _node(
            "encoder",
            input_sources={"prompt": "task.prompt"},
            output_field="description",
        ),
        _node(
            "decoder",
            input_sources={"description": "encoder.description"},
            output_field="code",
        ),
        terminal_node_id="decoder",
    )

    payload = graph.model_dump(mode="json")
    assert payload["nodes"][0]["input_sources"]["prompt"] == "task.prompt"
    assert payload["nodes"][1]["input_sources"]["description"] == (
        "encoder.description"
    )

    round_tripped = GraphConfig.model_validate(payload)
    assert round_tripped == graph
