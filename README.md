# dr-graph

Hashable treatment-description graphs plus a pure, deterministic
interpreter. Not a workflow engine.

The rule this library exists to serve: **whatever is searched over must be
data; whatever does the searching is code.** Graph specs are the
searched-over layer — experiment conditions, optimizer genomes. Optimizers
and durable workflows are ordinary code that read and write these specs.

## What it provides

- **Spec vocabulary** — `GraphSpec` (nodes + terminal node),
  `NodeSpec`/`NodeConfig` (typed input/output fields, input bindings,
  open parameters), and a binding-ref grammar
  (`task.prompt`, `encoder.description`). Node `op` and field `type_name`
  are open strings: the interpreter never dispatches on them, the injected
  callback does.
- **Structural validation** — acyclicity, ref legality, binding targets,
  terminal-node existence, deterministic topological ordering.
- **Pure sequential execution** — `execute_graph(graph=..., inputs=...,
  run_node=...)` resolves each node's inputs from external inputs plus
  upstream outputs and calls the injected `run_node` callback. Failed
  nodes mark downstream dependents blocked; independent branches continue.
  An optional `completed` mapping of node id → prior output skips
  already-paid-for nodes on resume.
- **Canonical digest** — `graph_digest(graph)` is the identity of the
  treatment; it covers the full spec including open `parameters`.
- **Neutral builders** — `node()` / `graph()` helpers, and
  `inline_subgraph()` for composing a subgraph into a parent graph.

Durability, retries, scheduling, persistence, prompts, and providers all
belong to the caller. Sequential execution is a feature: deterministic
order is what makes durable-workflow replay line up.

## Example

```python
from dr_graph import execute_graph, graph, node

spec = graph(
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

result = execute_graph(
    graph=spec,
    inputs={"prompt": "write an add function"},
    run_node=lambda node_spec, inputs: {
        "values": {node_spec.config.output_field: "..."}
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
