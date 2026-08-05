from __future__ import annotations

import pytest
from dr_serialize import StrictJsonError

from dr_graph import (
    FieldRole,
    GraphConfig,
    NodeConfig,
    NodeFieldSpec,
    graph_hash,
    validate_graph_external_inputs,
)
from dr_graph.identity import (
    GRAPH_CONFIG_IDENTITY_SCHEMA_VERSION,
    graph_config_identity_document,
)
from tests.support import _graph, _node

HASH_HEX_LENGTH = 64


def _graph_with_variable(value: object) -> GraphConfig:
    node = NodeConfig(
        node_id="direct",
        node_type="llm_call",
        fields=(NodeFieldSpec(name="output", role=FieldRole.OUTPUT),),
        output_field="output",
        variables={"x": value},
    )
    return _graph(node, terminal_node_id="direct")


def test_graph_hash_is_full_64_char_lowercase_hex() -> None:
    graph = _graph(_node("direct"), terminal_node_id="direct")
    digest = graph_hash(graph)
    assert len(digest) == HASH_HEX_LENGTH
    assert digest == digest.lower()
    assert all(char in "0123456789abcdef" for char in digest)


def test_graph_hash_uses_versioned_identity_document() -> None:
    graph = _graph(_node("direct"), terminal_node_id="direct")
    document = graph_config_identity_document(graph)
    assert document.schema == "dr_graph.graph_config"
    assert document.schema_version == GRAPH_CONFIG_IDENTITY_SCHEMA_VERSION


def test_graph_hash_is_stable_for_equivalent_graph_configs() -> None:
    graph = _graph(
        _node("direct", input_sources={"prompt": "task.prompt"}),
        terminal_node_id="direct",
    )
    same_graph = GraphConfig.model_validate(graph.model_dump(mode="json"))

    assert graph_hash(graph) == graph_hash(same_graph)


def test_graph_hash_does_not_depend_on_allowed_external_fields() -> None:
    graph = _graph(
        _node("direct", input_sources={"prompt": "task.prompt"}),
        terminal_node_id="direct",
    )
    digest = graph_hash(graph)
    validate_graph_external_inputs(graph, allowed_fields=("prompt",))
    validate_graph_external_inputs(
        graph,
        allowed_fields=("prompt", "task_id", "entry_point"),
    )
    assert graph_hash(graph) == digest


def test_graph_hash_changes_with_node_declaration_order() -> None:
    first = _graph(
        _node("a", input_sources={"seed": "b"}),
        _node("b"),
        terminal_node_id="a",
    )
    second = _graph(
        _node("b"),
        _node("a", input_sources={"seed": "b"}),
        terminal_node_id="a",
    )

    assert graph_hash(first) != graph_hash(second)


@pytest.mark.parametrize(
    "non_finite",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_graph_hash_rejects_non_finite_variable(non_finite: float) -> None:
    # Non-finite values must not collapse onto the same graph identity.
    graph = _graph_with_variable(non_finite)
    with pytest.raises(StrictJsonError):
        graph_hash(graph)


def test_graph_hash_accepts_list_variable_and_rejects_tuple() -> None:
    list_hash = graph_hash(_graph_with_variable([1, 2]))
    assert len(list_hash) == HASH_HEX_LENGTH
    with pytest.raises(StrictJsonError):
        graph_hash(_graph_with_variable((1, 2)))


def test_finite_variables_still_produce_distinct_hashes() -> None:
    none_hash = graph_hash(_graph_with_variable(None))
    finite_hash = graph_hash(_graph_with_variable(1.5))

    assert none_hash != finite_hash
