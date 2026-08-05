# dr-graph

[![CI](https://github.com/danielle-rothermel/dr-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/danielle-rothermel/dr-graph/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/dr-graph.svg)](https://pypi.org/project/dr-graph/)

| [Repo Definitions](https://danielle-rothermel.github.io/dr-graph/) | [dr-serialize v0.1.1](https://github.com/danielle-rothermel/dr-serialize) |
| --- | --- |

**dr-graph represents hashable computation graphs as data and interprets them
deterministically.** Graph structure is separate from caller-supplied node
behavior and is organized into these functional areas:

- **Definitions** describe nodes, connections, input and output fields, and
  tunable variables, then bind variable assignments into concrete graph
  configurations.
- **Configuration and validation** represent the fully set directed acyclic
  graph and enforce legal input sources and a single terminal node.
- **Identity** derives a versioned, canonical hash from every static field that
  defines a graph configuration.
- **Assembly and composition** provide neutral construction helpers and flatten
  reusable subgraphs into larger graphs.
- **Execution** resolves inputs and visits nodes in deterministic topological
  order while delegating each node's work to the caller.
- **Results and continuation** capture outputs, classified failures, blocked
  dependencies, and execution order, and accept completed node outputs to avoid
  repeating successful work.
