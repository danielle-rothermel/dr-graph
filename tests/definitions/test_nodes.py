from __future__ import annotations

import pytest

from dr_graph import FieldRole, NodeDefinition, NodeFieldSpec


def test_definition_rejects_unsourced_input_field() -> None:
    with pytest.raises(
        ValueError,
        match="input field\\(s\\) 'seed' have no input source",
    ):
        NodeDefinition(
            node_id="a",
            node_type="llm_call",
            fields=(
                NodeFieldSpec(name="seed", role=FieldRole.INPUT),
                NodeFieldSpec(name="out", role=FieldRole.OUTPUT),
            ),
            output_field="out",
        )
