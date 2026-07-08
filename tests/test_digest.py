from __future__ import annotations

import pytest

from dr_graph import GraphSpec, graph_digest, validate_external_bindings
from tests.support import _graph, _node


def test_graph_digest_rejects_invalid_length() -> None:
    graph = _graph(_node("direct"), terminal_node_id="direct")
    with pytest.raises(ValueError, match="digest length must be"):
        graph_digest(graph, length=0)
    with pytest.raises(ValueError, match="digest length must be"):
        graph_digest(graph, length=-1)
    with pytest.raises(ValueError, match="digest length must be"):
        graph_digest(graph, length=65)


def test_graph_digest_is_stable_for_equivalent_graph_specs() -> None:
    graph = _graph(
        _node("direct", bindings={"prompt": "task.prompt"}),
        terminal_node_id="direct",
    )
    same_graph = GraphSpec.model_validate(graph.model_dump(mode="json"))

    assert graph_digest(graph) == graph_digest(same_graph)


def test_graph_digest_does_not_depend_on_allowed_external_fields() -> None:
    graph = _graph(
        _node("direct", bindings={"prompt": "task.prompt"}),
        terminal_node_id="direct",
    )
    digest = graph_digest(graph)
    validate_external_bindings(graph, allowed_fields=("prompt",))
    validate_external_bindings(
        graph,
        allowed_fields=("prompt", "task_id", "entry_point"),
    )
    assert graph_digest(graph) == digest


def test_graph_digest_changes_with_node_declaration_order() -> None:
    first = _graph(_node("a"), _node("b"), terminal_node_id="a")
    second = _graph(_node("b"), _node("a"), terminal_node_id="a")

    assert first.topological_order() == tuple(
        sorted(first.nodes, key=lambda n: n.id)
    )
    assert graph_digest(first) != graph_digest(second)
