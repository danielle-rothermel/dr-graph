from __future__ import annotations

import pytest

from dr_graph import FieldRole, NodeConfig, NodeFieldSpec, NodeInputSourceRef
from tests.support import _node


def test_node_config_requires_declared_fields() -> None:
    with pytest.raises(
        ValueError,
        match="node config must declare at least one field",
    ):
        NodeConfig(
            node_id="n",
            node_type="llm_call",
            fields=(),
            output_field="output",
        )


def test_node_config_rejects_duplicate_field_names() -> None:
    with pytest.raises(ValueError, match="duplicate field names"):
        NodeConfig(
            node_id="n",
            node_type="llm_call",
            fields=(
                NodeFieldSpec(name="output", role=FieldRole.OUTPUT),
                NodeFieldSpec(name="output", role=FieldRole.OUTPUT),
            ),
            output_field="output",
        )


def test_node_config_rejects_unknown_output_field() -> None:
    with pytest.raises(
        ValueError,
        match="output_field 'missing' is not an output field",
    ):
        NodeConfig(
            node_id="n",
            node_type="llm_call",
            fields=(NodeFieldSpec(name="output", role=FieldRole.OUTPUT),),
            output_field="missing",
        )


def test_node_config_rejects_source_to_undeclared_input_field() -> None:
    with pytest.raises(
        ValueError,
        match="input source 'prompt' is not an input field",
    ):
        NodeConfig(
            node_id="n",
            node_type="llm_call",
            fields=(NodeFieldSpec(name="output", role=FieldRole.OUTPUT),),
            input_sources={
                "prompt": NodeInputSourceRef.model_validate("task.prompt")
            },
            output_field="output",
        )


def test_node_config_rejects_input_field_without_source() -> None:
    with pytest.raises(
        ValueError,
        match="input field\\(s\\) 'prompt' have no input source",
    ):
        NodeConfig(
            node_id="n",
            node_type="llm_call",
            fields=(
                NodeFieldSpec(name="prompt", role=FieldRole.INPUT),
                NodeFieldSpec(name="output", role=FieldRole.OUTPUT),
            ),
            output_field="output",
        )


def test_node_id_rejects_ref_grammar_tokens() -> None:
    with pytest.raises(ValueError, match=r"cannot contain '\.'"):
        _node("a.b")
    with pytest.raises(ValueError, match=r"'task' is reserved"):
        _node("task")
