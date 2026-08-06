# dr-graph

[![CI](https://github.com/danielle-rothermel/dr-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/danielle-rothermel/dr-graph/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/dr-graph.svg)](https://pypi.org/project/dr-graph/)

| [Terms and contracts](https://danielle-rothermel.github.io/dr-graph/) | [Terms TOML](https://github.com/danielle-rothermel/dr-graph/blob/main/.defs/terms.toml) | [Contracts TOML](https://github.com/danielle-rothermel/dr-graph/blob/main/.defs/contracts.toml) | [dr-serialize](https://github.com/danielle-rothermel/dr-serialize) |
| --- | --- | --- | --- |

**dr-graph represents hashable computation graphs as data, interprets them
deterministically, and provides exact flow optimization primitives.** Graph
structure is separate from caller-supplied node behavior and optimization.

- **[Definitions](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/definitions)**
  describe reusable graph topology, node fields, dependencies, and variable
  requirements.
- **[Configuration](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/configuration)**
  models concrete variable values and validates the resulting graph.
- **[Identity](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/identity)**
  gives every complete graph configuration a stable, versioned identity.
- **[Execution](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/execution)**
  interprets a graph in topological order while delegating node behavior to
  the caller.
- **[Results](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/results)**
  models per-node and graph-level outcomes, including reuse of completed node
  outputs when continuing execution.
- **[Flow optimization](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/flow)**
  solves exact min-cost flow and balanced separable convex transportation
  problems independently of computation-graph execution.
- **Infra**
  - **[Assembly](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/assembly)**
    creates graphs programmatically, including deterministic namespacing and
    rewiring of subgraphs.
  - **[Core](https://github.com/danielle-rothermel/dr-graph/tree/main/src/dr_graph/core)**
    contains shared errors, field and input-source models, topology helpers,
    and strict-JSON validation.

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
    schema_version: Literal[1] = 1
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
    attempt_evidence_refs: tuple[str, ...]
    provenance: dict[str, Jsonable]
```

## Flow optimization

Flow optimization is independent of graph configuration and interpretation.
The base package models declared network order and returns exact arc flows in
that order.

```python
class FlowArc:
    arc_id: ArcId
    source: NodeId
    target: NodeId
    capacity: int
    unit_cost: int


class FlowProblem:
    nodes: tuple[NodeId, ...]
    arcs: tuple[FlowArc, ...]
    source: NodeId
    sink: NodeId
    required_flow: int


class FlowResult:
    sent_flow: int
    total_cost: int
    arc_flows: tuple[ArcFlow, ...]
```

```python
def solve_min_cost_flow(problem: FlowProblem) -> FlowResult: ...
```

The nested transportation package models each available route by its ordered
marginal costs; every entry supplies one unit of capacity. Its result preserves
source and destination index order as an allocation matrix.

```python
class TransportCell:
    source_index: int
    destination_index: int
    marginal_costs: tuple[int, ...]


class TransportProblem:
    supplies: tuple[int, ...]
    demands: tuple[int, ...]
    cells: tuple[TransportCell, ...]


class TransportSolution:
    allocations: tuple[tuple[int, ...], ...]
    total_flow: int
    total_cost: int
```

```python
def solve_separable_transport(
    problem: TransportProblem,
) -> TransportSolution: ...
```
