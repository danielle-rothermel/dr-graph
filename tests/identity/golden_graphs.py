"""Canonical golden Graph Configs for the graph_hash identity gate.

These mirror the original whetstone extraction fixtures, re-expressed under
the target GraphConfig / Node Input Source / Variable model. They are the
source of truth for `tests/identity/fixtures/graph_hashes_golden.json`;
regenerate the fixture with `python -m tests.identity.regen_golden_hashes`
after an intentional identity change (a coordinated break), never to paper
over a mismatch.
"""

from __future__ import annotations

from dr_graph import GraphConfig, graph, node


def direct_graph() -> GraphConfig:
    return graph(
        [
            node(
                "direct",
                node_type="llm_call",
                input_sources={"prompt": "task.prompt"},
                output_field="output",
                variables={"user_prompt_template": "{prompt}"},
            ),
        ],
        terminal="direct",
    )


def encdec_graph() -> GraphConfig:
    return graph(
        [
            node(
                "encoder",
                node_type="llm_call",
                input_sources={"prompt": "task.prompt"},
                output_field="description",
                variables={
                    "provider_config_id": "encoder",
                    "user_prompt_template": "Describe {prompt}",
                },
            ),
            node(
                "decoder",
                node_type="llm_call",
                input_sources={"description": "encoder.description"},
                output_field="code",
                variables={
                    "provider_config_id": "decoder",
                    "user_prompt_template": "Write code from {description}",
                },
            ),
        ],
        terminal="decoder",
    )


def humaneval_encdec_graph() -> GraphConfig:
    encoder_template = (
        "{instructions_start}\n"
        "Use at most {budget} characters.\n\n"
        "```python\n{gt_code}\n```\n{instructions_end}"
    )
    decoder_template = (
        "Write functional code in Python according to the following "
        "description.\nOutput only the final answer, without any descriptions "
        "or surrounding\ncharacters.\n\n{encoded_desc}"
    )
    return graph(
        [
            node(
                "encoder",
                node_type="llm_call",
                input_sources={
                    "instructions_start": "task.instructions_start",
                    "budget": "task.budget",
                    "gt_code": "task.gt_code",
                    "instructions_end": "task.instructions_end",
                },
                output_field="description",
                variables={
                    "provider_config_id": "encoder",
                    "user_prompt_template": encoder_template,
                },
            ),
            node(
                "decoder",
                node_type="llm_call",
                input_sources={"encoded_desc": "encoder.description"},
                output_field="code",
                variables={
                    "provider_config_id": "decoder",
                    "user_prompt_template": decoder_template,
                },
            ),
        ],
        terminal="decoder",
    )


GOLDEN_GRAPHS: dict[str, GraphConfig] = {
    "direct_graph": direct_graph(),
    "encdec_graph": encdec_graph(),
    "humaneval_encdec_graph": humaneval_encdec_graph(),
}
