"""Fixed external-input namespace (task)."""

from __future__ import annotations

import pytest

from dr_graph import BindingRef, BindingSource, node


def test_task_refs_parse_as_external() -> None:
    ref = BindingRef.model_validate("task.prompt")
    assert ref.source is BindingSource.EXTERNAL
    assert ref.field == "prompt"
    assert ref.ref == "task.prompt"


def test_other_heads_parse_as_node_refs() -> None:
    ref = BindingRef.model_validate("encoder.prompt")
    assert ref.source is BindingSource.NODE
    assert ref.node_id == "encoder"
    assert ref.field == "prompt"
    assert ref.ref == "encoder.prompt"


def test_task_is_rejected_as_node_id() -> None:
    with pytest.raises(ValueError, match=r"'task' is reserved"):
        node("task", op="llm_call", output_field="output")


def test_identifiers_containing_dot_are_rejected() -> None:
    with pytest.raises(ValueError, match=r"cannot contain '\.'"):
        node("encoder.v1", op="llm_call", output_field="output")

    with pytest.raises(ValueError, match=r"cannot contain '\.'"):
        BindingRef.model_validate(
            {"source": "node", "node_id": "encoder.v1"}
        )


def test_binding_ref_rejects_empty_node_field() -> None:
    with pytest.raises(ValueError, match="non-empty field"):
        BindingRef.model_validate("encoder.")


def test_binding_ref_rejects_reserved_node_id() -> None:
    with pytest.raises(ValueError, match=r"'task' is reserved"):
        BindingRef.model_validate("task")


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        (
            {"source": "external", "field": "prompt", "node_id": "n1"},
            "external binding refs cannot include node_id",
        ),
        (
            {"source": "external", "field": ""},
            "external binding refs require a field",
        ),
        (
            {"source": "external"},
            "external binding refs require a field",
        ),
        (
            {"source": "node", "field": "out"},
            "node binding refs require node_id",
        ),
        (
            {"source": "node", "node_id": "", "field": "out"},
            "node binding refs require node_id",
        ),
        (
            {"source": "node", "node_id": "enc", "field": ""},
            "non-empty field",
        ),
        (
            {"source": "node", "node_id": "task"},
            "'task' is reserved",
        ),
        (
            {"source": "node", "node_id": "a.b"},
            "cannot contain '.'",
        ),
    ],
)
def test_binding_ref_rejects_invalid_dict_shapes(
    payload: dict[str, str],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        BindingRef.model_validate(payload)
