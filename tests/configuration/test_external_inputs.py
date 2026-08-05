from __future__ import annotations

import pytest

from dr_graph import validate_graph_external_inputs
from tests.support import _graph, _node


def test_unknown_task_input_field_validation() -> None:
    graph = _graph(
        _node("direct", input_sources={"prompt": "task.promt"}),
        terminal_node_id="direct",
    )
    with pytest.raises(
        ValueError,
        match=(
            "graph external input\\(s\\) 'promt' not in allowed "
            "external fields"
        ),
    ):
        validate_graph_external_inputs(graph, allowed_fields=("prompt",))


def test_graph_with_task_sources_does_not_require_task_fields() -> None:
    graph = _graph(
        _node("direct", input_sources={"prompt": "task.prompt"}),
        terminal_node_id="direct",
    )
    assert graph.model_dump(mode="json")["nodes"]
    validate_graph_external_inputs(graph, allowed_fields=("prompt",))
