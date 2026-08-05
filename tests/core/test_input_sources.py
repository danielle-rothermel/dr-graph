"""Fixed external-input namespace (task)."""

from __future__ import annotations

import pytest

from dr_graph import NodeInputSourceKind, NodeInputSourceRef, node


def test_task_refs_parse_as_external() -> None:
    ref = NodeInputSourceRef.model_validate("task.prompt")
    assert ref.kind is NodeInputSourceKind.GRAPH_EXTERNAL
    assert ref.field == "prompt"
    assert ref.ref == "task.prompt"


def test_other_heads_parse_as_node_refs() -> None:
    ref = NodeInputSourceRef.model_validate("encoder.prompt")
    assert ref.kind is NodeInputSourceKind.NODE_OUTPUT
    assert ref.node_id == "encoder"
    assert ref.field == "prompt"
    assert ref.ref == "encoder.prompt"


def test_task_is_rejected_as_node_id() -> None:
    with pytest.raises(ValueError, match=r"'task' is reserved"):
        node("task", node_type="llm_call", output_field="output")


def test_identifiers_containing_dot_are_rejected() -> None:
    with pytest.raises(ValueError, match=r"cannot contain '\.'"):
        node("encoder.v1", node_type="llm_call", output_field="output")

    with pytest.raises(ValueError, match=r"cannot contain '\.'"):
        NodeInputSourceRef.model_validate(
            {"kind": "node_output", "node_id": "encoder.v1"}
        )


def test_input_source_rejects_empty_node_field() -> None:
    with pytest.raises(ValueError, match="non-empty field"):
        NodeInputSourceRef.model_validate("encoder.")


def test_input_source_rejects_reserved_node_id() -> None:
    with pytest.raises(ValueError, match=r"'task' is reserved"):
        NodeInputSourceRef.model_validate("task")


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        (
            {"kind": "graph_external", "field": "prompt", "node_id": "n1"},
            "graph external input sources cannot include node_id",
        ),
        (
            {"kind": "graph_external", "field": ""},
            "graph external input sources require a field",
        ),
        (
            {"kind": "graph_external"},
            "graph external input sources require a field",
        ),
        (
            {"kind": "node_output", "field": "out"},
            "node output input sources require node_id",
        ),
        (
            {"kind": "node_output", "node_id": "", "field": "out"},
            "node output input sources require node_id",
        ),
        (
            {"kind": "node_output", "node_id": "enc", "field": ""},
            "non-empty field",
        ),
        (
            {"kind": "node_output", "node_id": "task"},
            "'task' is reserved",
        ),
        (
            {"kind": "node_output", "node_id": "a.b"},
            "cannot contain '.'",
        ),
    ],
)
def test_input_source_rejects_invalid_dict_shapes(
    payload: dict[str, str],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        NodeInputSourceRef.model_validate(payload)
