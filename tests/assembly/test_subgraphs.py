from __future__ import annotations

import pytest

from dr_graph import (
    GraphRunStatus,
    execute_graph,
    graph,
    inline_subgraph,
    node,
)
from dr_graph.assembly import prefixed_node_id


def _encdec_subgraph():
    return graph(
        [
            node(
                "encoder",
                node_type="llm_call",
                input_sources={"prompt": "task.prompt"},
                output_field="description",
            ),
            node(
                "decoder",
                node_type="llm_call",
                input_sources={"description": "encoder.description"},
                output_field="code",
            ),
        ],
        terminal="decoder",
    )


def test_inline_subgraph_prefixes_ids_and_rewires_internal_refs() -> None:
    nodes = inline_subgraph(_encdec_subgraph(), prefix="inner")

    assert [n.node_id for n in nodes] == ["inner:encoder", "inner:decoder"]
    decoder = nodes[1]
    assert decoder.input_sources["description"].ref == (
        "inner:encoder.description"
    )
    # Unmapped external inputs pass through.
    encoder = nodes[0]
    assert encoder.input_sources["prompt"].ref == "task.prompt"


def test_inline_subgraph_rebinds_external_inputs() -> None:
    parent_source = node(
        "seed",
        node_type="llm_call",
        input_sources={"prompt": "task.prompt"},
        output_field="idea",
    )
    inner = inline_subgraph(
        _encdec_subgraph(),
        prefix="inner",
        input_sources={"prompt": "seed.idea"},
    )
    config = graph(
        [parent_source, *inner],
        terminal=prefixed_node_id("inner", "decoder"),
    )

    result = execute_graph(
        graph=config,
        inputs={"prompt": "adder"},
        run_node=lambda node_config, inputs: {
            "values": {
                node_config.output_field: (
                    f"{node_config.node_id}"
                    f"({', '.join(sorted(inputs.values()))})"
                )
            }
        },
    )
    assert result.status is GraphRunStatus.SUCCESS
    assert result.terminal_output == (
        "inner:decoder(inner:encoder(seed(adder)))"
    )


def test_inline_subgraph_composed_graph_hash_is_flattened_config() -> None:
    inner = inline_subgraph(_encdec_subgraph(), prefix="inner")
    composed = graph(list(inner), terminal="inner:decoder")

    from dr_graph import GraphConfig, graph_hash

    manual = GraphConfig.model_validate(composed.model_dump(mode="json"))
    assert composed == manual
    assert graph_hash(composed) == graph_hash(manual)


def test_inline_subgraph_rejects_unknown_input_source() -> None:
    with pytest.raises(ValueError, match="not external inputs"):
        inline_subgraph(
            _encdec_subgraph(),
            prefix="inner",
            input_sources={"nope": "seed.idea"},
        )


def test_inline_subgraph_rejects_bad_prefix_and_separator() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        inline_subgraph(_encdec_subgraph(), prefix="")
    with pytest.raises(ValueError, match=r"cannot contain '\.'"):
        inline_subgraph(_encdec_subgraph(), prefix="a.b")
    with pytest.raises(ValueError, match=r"cannot contain '\.'"):
        inline_subgraph(_encdec_subgraph(), prefix="ok", separator=".")


def test_inline_subgraph_preserves_node_types_and_variables() -> None:
    sub = graph(
        [
            node(
                "score",
                node_type="tool_call",
                input_sources={"code": "task.code"},
                output_field="score",
                variables={"threshold": 0.5, "note": "keep"},
            ),
        ],
        terminal="score",
    )
    (inlined,) = inline_subgraph(sub, prefix="s")
    assert inlined.node_type == "tool_call"
    assert inlined.variables == {"threshold": 0.5, "note": "keep"}
