# dr-graph

Hashable computation-graph configurations plus a pure, deterministic
interpreter. Graph structure is data; node behavior is caller-supplied code.
This library is not a workflow engine.

## At a Glance

- **Documentation:** [Vocabulary and contract reference](https://danielle-rothermel.github.io/dr-graph/)
- **Personally maintained dependencies:**
  - [dr-serialize](https://github.com/danielle-rothermel/dr-serialize) — current
    release `0.1.1`; this repository accepts `0.1.x` and locks `0.1.0`

## High-level design

- **Graph definitions** describe nodes, connections, input and output fields,
  and tunable variables, then bind variable assignments into concrete graph
  configurations.
- **Configuration and validation** represent the fully set directed acyclic
  graph and enforce its structural rules, including legal input sources and a
  single terminal node.
- **Stable identity** derives a versioned, canonical hash from every static
  field that defines a graph configuration.
- **Assembly and composition** provide neutral construction helpers and let
  reusable subgraphs be flattened into a larger graph without introducing a
  separate runtime layer.
- **Deterministic interpretation** resolves inputs and visits nodes in
  topological order, delegating each node's actual work to a callback supplied
  by the caller.
- **Run results and continuation** capture outputs, classified failures,
  blocked dependencies, and execution order; callers may provide completed
  node outputs to avoid repeating successful work.

The library owns graph data, validation, identity, interpretation, and result
shapes. Callers own durability, retries, scheduling, persistence, prompts, and
provider integrations.

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
