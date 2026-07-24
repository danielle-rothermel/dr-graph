# dr-graph

Hashable computation-graph configs plus a pure, deterministic
interpreter. Not a workflow engine.

The rule this library exists to serve: **whatever is searched over must
be data; whatever does the searching is code.** Graph configs are the
searched-over layer — the motivating use case is experiment conditions
and optimizer genomes. Optimizers and durable workflows are ordinary
code that read and write these configs.

The [vocabulary sheet](https://danielle-rothermel.github.io/dr-graph/)
(source: `.defs/vocab.html`) is the authoritative contract: the terms,
guarantees, scope boundaries, and the mapping from each term to the
exported names. This README orients; the sheet decides.

## What it provides

- **`GraphDefinition` / `NodeDefinition`** — a versioned,
  variable-bearing DAG shape that `materialize()`s fully-set
  `GraphConfig`s from per-node Variable assignments.
- **`GraphConfig` / `NodeConfig`** — the flat, validated config that a
  graph hash identifies; construction enforces the structural
  guarantees (acyclicity, exactly one terminal node, input-source
  legality).
- **`graph_hash()`** — the config's identity, computed through
  dr-serialize's identity API; the sheet defines its exact coverage
  and format.
- **`execute_graph()`** — pure sequential execution: resolves each
  node's inputs, calls the injected `run_node` callback, and returns a
  `GraphRunResult`. An optional `completed` mapping skips
  already-paid-for nodes on resume.
- **`node()` / `graph()` / `inline_subgraph()`** — neutral builders and
  composition by flattening.

Everything else — durability, retries, scheduling, persistence,
prompts, providers — belongs to the caller; the sheet draws the exact
line. Sequential execution is a feature: deterministic order is what
makes durable-workflow replay line up.

## Ecosystem

Part of the `dr-*` family: depends on `dr-serialize` (identity
hashing); consumed by `whetstone-ai`. Neighbor repos are
`dr-providers`, `dr-platform`, `dr-code`, and `unitbench`.

## Example

```python
from dr_graph import execute_graph, graph, node

config = graph(
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

result = execute_graph(
    graph=config,
    inputs={"prompt": "write an add function"},
    run_node=lambda node_config, inputs: {
        "values": {node_config.output_field: "..."}
    },
)
```

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ty check
```
