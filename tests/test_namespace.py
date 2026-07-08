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
