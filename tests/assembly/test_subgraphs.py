from __future__ import annotations

import pytest

from dr_graph import (
    FieldRole,
    GraphConfig,
    GraphRunStatus,
    NodeConfig,
    NodeFieldSpec,
    NodeInputSourceRef,
    execute_graph,
    graph,
    graph_hash,
    inline_subgraph,
    node,
)
from dr_graph.assembly import prefixed_node_id
from tests.support import encdec_graph


def test_inline_subgraph_prefixes_ids_and_rewires_internal_refs() -> None:
    nodes = inline_subgraph(encdec_graph(), prefix="inner")

    assert [n.node_id for n in nodes] == ["inner:encoder", "inner:decoder"]
    decoder = nodes[1]
    assert decoder.input_sources["description"].ref == (
        "inner:encoder.description"
    )
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
        encdec_graph(),
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
    inner = inline_subgraph(encdec_graph(), prefix="inner")
    composed = graph(list(inner), terminal="inner:decoder")
    expected = GraphConfig(
        nodes=(
            NodeConfig(
                node_id="inner:encoder",
                node_type="llm_call",
                fields=(
                    NodeFieldSpec(name="prompt", role=FieldRole.INPUT),
                    NodeFieldSpec(
                        name="description",
                        role=FieldRole.OUTPUT,
                    ),
                ),
                input_sources={
                    "prompt": NodeInputSourceRef.model_validate("task.prompt")
                },
                output_field="description",
            ),
            NodeConfig(
                node_id="inner:decoder",
                node_type="llm_call",
                fields=(
                    NodeFieldSpec(
                        name="description",
                        role=FieldRole.INPUT,
                    ),
                    NodeFieldSpec(name="code", role=FieldRole.OUTPUT),
                ),
                input_sources={
                    "description": NodeInputSourceRef.model_validate(
                        "inner:encoder.description"
                    )
                },
                output_field="code",
            ),
        ),
        terminal_node_id="inner:decoder",
    )

    assert composed == expected
    assert graph_hash(composed) == graph_hash(expected)


def test_inline_subgraph_rejects_unknown_input_source() -> None:
    with pytest.raises(ValueError, match="not external inputs"):
        inline_subgraph(
            encdec_graph(),
            prefix="inner",
            input_sources={"nope": "seed.idea"},
        )


@pytest.mark.parametrize(
    ("prefix", "separator", "error_match"),
    [
        pytest.param("", ":", "non-empty", id="empty-prefix"),
        pytest.param(
            "a.b",
            ":",
            r"cannot contain '\.'",
            id="dotted-prefix",
        ),
        pytest.param(
            "ok",
            ".",
            r"cannot contain '\.'",
            id="dotted-separator",
        ),
    ],
)
def test_inline_subgraph_rejects_bad_prefix_and_separator(
    prefix: str,
    separator: str,
    error_match: str,
) -> None:
    with pytest.raises(ValueError, match=error_match):
        inline_subgraph(
            encdec_graph(),
            prefix=prefix,
            separator=separator,
        )


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
