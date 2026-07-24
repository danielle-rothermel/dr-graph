# dr-graph

Hashable computation-graph configs plus a pure, deterministic
interpreter. Not a workflow engine.

The rule this library exists to serve: **whatever is searched over must be
data; whatever does the searching is code.** Graph configs are the
searched-over layer — the motivating use case is experiment conditions and
optimizer genomes. Optimizers and durable workflows are ordinary code that
read and write these configs.

The [vocabulary sheet](https://danielle-rothermel.github.io/dr-graph/)
(source: `.defs/vocab.html`) is the authoritative statement of the
computation-graph contract this repo implements: the terms, the
guarantees, what is in and out of scope, and the mapping from each term to
the exported names.

## Ecosystem

dr-graph defines the versioned, variable-bearing Graph Definition artifact,
hashable Graph Configs, and a pure deterministic interpreter; Graph Configs
are searched-over experiment treatments, with `graph_hash` as treatment
identity. Neighbor repos are `dr-serialize`, `dr-providers`, `dr-platform`,
`dr-code`, `whetstone-ai`, and `unitbench`. It depends on `dr-serialize`;
`whetstone-ai` consumes it.

## What it provides

- **Graph Definition artifact** — `GraphDefinition` / `NodeDefinition`: a
  versioned, variable-bearing DAG shape that declares Node Definitions,
  Variables, structure, input/output contracts, and exactly one terminal
  Node, and `materialize()`s one or more fully-set `GraphConfig`s.
- **Config vocabulary** — `GraphConfig` (nodes + terminal node),
  `NodeConfig` (typed input/output fields, Node Input Sources, open
  Variable assignments), `NodeFieldSpec`, and a Node Input Source grammar
  (`task.prompt`, `encoder.description`) via `NodeInputSourceRef` /
  `NodeInputSourceKind` (`GRAPH_EXTERNAL` / `NODE_OUTPUT`). Node
  `node_type` and field `type_name` are open strings: the interpreter never
  dispatches on them, the injected callback does.
- **Structural validation** — acyclicity, input-source legality, source
  targets, terminal-node existence, exactly one terminal/sink Node,
  deterministic topological ordering.
- **Pure sequential execution** — `execute_graph(graph=..., inputs=...,
  run_node=...)` resolves each node's inputs from Graph External Inputs plus
  upstream Node Outputs and calls the injected `run_node` callback. Failed
  nodes mark downstream dependents blocked. An optional `completed` mapping
  of node id → prior output skips already-paid-for nodes on resume. It
  returns a `GraphRunResult` carrying the run's `graph_hash`, external
  inputs, terminal outcome, and per-Node outcomes/order.
- **Graph Hash** — `graph_hash(graph)` is the identity of the treatment: the
  full 64-char lowercase SHA-256 Identity Hash of the Graph Config Identity
  Document, computed through dr-serialize's identity API. It covers every
  identity-bearing field including open Variable assignments.
- **Neutral builders** — `node()` / `graph()` helpers, and
  `inline_subgraph()` for composing a subgraph into a parent graph.

Durability, retries, scheduling, persistence, prompts, and providers all
belong to the caller. Sequential execution is a feature: deterministic
order is what makes durable-workflow replay line up.

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
