# dr-graph

[![CI](https://github.com/danielle-rothermel/dr-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/danielle-rothermel/dr-graph/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/dr-graph.svg)](https://pypi.org/project/dr-graph/)

| [Repo Definitions](https://danielle-rothermel.github.io/dr-graph/) | [dr-serialize v0.1.1](https://github.com/danielle-rothermel/dr-serialize) |
| --- | --- |

**dr-graph represents hashable computation graphs as data and interprets them
deterministically.** Graph structure is separate from caller-supplied node
behavior.

- **[Definitions](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/definitions)**
  describe reusable graph topology, node fields, dependencies, and variable
  requirements.
- **[Configuration](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/configuration)**
  materializes definitions with concrete variable values and validates the
  resulting graph.
- **[Identity](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/identity)**
  gives every complete graph configuration a stable, versioned identity.
- **[Execution](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/execution)**
  interprets a graph in topological order while delegating node behavior to
  the caller.
- **[Results](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/results)**
  models per-node and graph-level outcomes, including reuse of completed node
  outputs when continuing execution.
- **Infra**
  - **[Assembly](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/assembly)**
    creates graphs programmatically, including deterministic namespacing and
    rewiring of subgraphs.
  - **[Core](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/core)**
    contains shared validation, ordering, naming, and normalization
    infrastructure.

The following sketches show the public contract shapes. Validation and
implementation details are omitted.

## Definitions

Definitions describe reusable graph topology before concrete variable values
are supplied. Materialization binds those values and produces an executable
graph configuration.

```python
class NodeDefinition(BaseModel):
    node_id: str
    node_type: str
    fields: tuple[NodeFieldSpec, ...]
    input_sources: dict[str, NodeInputSourceRef]
    output_field: str
    variable_names: frozenset[str]


class GraphDefinition(BaseModel):
    schema_version: int
    nodes: tuple[NodeDefinition, ...]
    terminal_node_id: str
```

```python
def materialize(
    self,
    variable_assignments: Mapping[str, Mapping[str, Any]] | None = None,
) -> GraphConfig: ...
```

## Configuration

Configurations are complete, validated graphs with concrete values. Their
dependency structure has a deterministic topological order.

```python
class NodeConfig(BaseModel):
    node_id: str
    node_type: str
    fields: tuple[NodeFieldSpec, ...]
    input_sources: dict[str, NodeInputSourceRef]
    output_field: str
    variables: dict[str, Any]


class GraphConfig(BaseModel):
    nodes: tuple[NodeConfig, ...]
    terminal_node_id: str

    def topological_order(self) -> tuple[NodeConfig, ...]: ...
```

```python
def validate_graph_external_inputs(
    graph: GraphConfig,
    *,
    allowed_fields: Collection[str],
) -> None: ...
```

## Identity

Every static configuration field participates in a versioned canonical
identity document. `dr-serialize` turns that document into the graph's full
SHA-256 hash.

```python
GRAPH_CONFIG_IDENTITY_SCHEMA = "dr_graph.graph_config"
GRAPH_CONFIG_IDENTITY_SCHEMA_VERSION = 1


def graph_config_identity_document(
    graph: GraphConfig,
) -> IdentityDocument: ...


def graph_hash(graph: GraphConfig) -> str: ...
```

## Execution

Execution owns graph traversal and dependency wiring while the caller owns
node behavior. A dependency-closed set of completed node outputs may be
supplied to continue execution.

```python
type RunNode = Callable[
    [NodeConfig, Mapping[str, Any]],
    NodeOutput | Mapping[str, Any],
]
```

```python
def execute_graph(
    *,
    graph: GraphConfig,
    inputs: Mapping[str, Any],
    run_node: RunNode,
    completed: Mapping[str, NodeOutput | Mapping[str, Any]] | None = None,
) -> GraphRunResult: ...
```

## Results

Results distinguish node outcomes from the aggregate graph outcome and retain
enough structured state to inspect or continue a run.

```python
class NodeOutcomeStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"


class GraphRunStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"
```

```python
class NodeOutput(BaseModel):
    values: dict[str, Jsonable]
    metadata: dict[str, Jsonable]


class NodeOutcome(BaseModel):
    node_id: str
    status: NodeOutcomeStatus
    output: NodeOutput | None
    error: NodeError | None
    blocked_by: tuple[str, ...]
```

```python
class GraphRunResult(BaseModel):
    graph_hash: str
    external_inputs: dict[str, Jsonable]
    status: GraphRunStatus
    outcomes: dict[str, NodeOutcome]
    execution_order: tuple[str, ...]
    terminal_node_id: str
    terminal_output: Jsonable
    terminal_error: TerminalError | None
    provenance: dict[str, Jsonable]
```
