from __future__ import annotations

import pytest

from dr_graph import (
    GraphRunStatus,
    execute_graph,
    graph,
    inline_subgraph,
    node,
)
from dr_graph.compose import prefixed_node_id


def _encdec_subgraph():
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


def test_inline_subgraph_prefixes_ids_and_rewires_internal_refs() -> None:
    nodes = inline_subgraph(_encdec_subgraph(), prefix="inner")

    assert [n.id for n in nodes] == ["inner:encoder", "inner:decoder"]
    decoder = nodes[1]
    assert decoder.config.input_bindings["description"].ref == (
        "inner:encoder.description"
    )
    # Unmapped external inputs pass through.
    encoder = nodes[0]
    assert encoder.config.input_bindings["prompt"].ref == "task.prompt"


def test_inline_subgraph_rebinds_external_inputs() -> None:
    parent_source = node(
        "seed",
        op="llm_call",
        bindings={"prompt": "task.prompt"},
        output_field="idea",
    )
    inner = inline_subgraph(
        _encdec_subgraph(),
        prefix="inner",
        bindings={"prompt": "seed.idea"},
    )
    spec = graph(
        [parent_source, *inner],
        terminal=prefixed_node_id("inner", "decoder"),
    )

    result = execute_graph(
        graph=spec,
        inputs={"prompt": "adder"},
        run_node=lambda node_spec, inputs: {
            "values": {
                node_spec.config.output_field: (
                    f"{node_spec.id}({', '.join(sorted(inputs.values()))})"
                )
            }
        },
    )
    assert result.status is GraphRunStatus.SUCCESS
    assert result.terminal_output == (
        "inner:decoder(inner:encoder(seed(adder)))"
    )


def test_inline_subgraph_composed_graph_digest_is_flattened_spec() -> None:
    inner = inline_subgraph(_encdec_subgraph(), prefix="inner")
    composed = graph(list(inner), terminal="inner:decoder")

    from dr_graph import GraphSpec

    manual = GraphSpec.model_validate(composed.model_dump(mode="json"))
    assert composed == manual


def test_inline_subgraph_rejects_unknown_binding() -> None:
    with pytest.raises(ValueError, match="not external inputs"):
        inline_subgraph(
            _encdec_subgraph(),
            prefix="inner",
            bindings={"nope": "seed.idea"},
        )


def test_inline_subgraph_rejects_bad_prefix_and_separator() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        inline_subgraph(_encdec_subgraph(), prefix="")
    with pytest.raises(ValueError, match=r"cannot contain '\.'"):
        inline_subgraph(_encdec_subgraph(), prefix="a.b")
    with pytest.raises(ValueError, match=r"cannot contain '\.'"):
        inline_subgraph(_encdec_subgraph(), prefix="ok", separator=".")


def test_inline_subgraph_preserves_ops_and_parameters() -> None:
    sub = graph(
        [
            node(
                "score",
                op="tool_call",
                bindings={"code": "task.code"},
                output_field="score",
                parameters={"threshold": 0.5, "note": "keep"},
            ),
        ],
        terminal="score",
    )
    (inlined,) = inline_subgraph(sub, prefix="s")
    assert inlined.op == "tool_call"
    assert inlined.config.parameters == {"threshold": 0.5, "note": "keep"}
