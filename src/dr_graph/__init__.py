"""Hashable computation-graph specs plus a pure, deterministic interpreter."""

from dr_graph.builders import as_binding_ref, graph, node
from dr_graph.compose import inline_subgraph
from dr_graph.errors import (
    CompletedNodeError,
    GraphExecutionError,
    GraphValidationError,
    InputResolutionError,
    NodeExecutionError,
)
from dr_graph.execution import (
    RunNode,
    execute_graph,
    resolve_node_inputs,
)
from dr_graph.hashing import (
    canonical_graph_payload,
    graph_digest,
)
from dr_graph.refs import (
    BindingRef,
    BindingSource,
)
from dr_graph.results import (
    ClassifiedFailure,
    GraphRunResult,
    GraphRunStatus,
    NodeError,
    NodeOutcome,
    NodeOutcomeStatus,
    NodeOutput,
    TerminalError,
)
from dr_graph.spec import (
    FieldRole,
    FieldSpec,
    GraphSpec,
    NodeConfig,
    NodeSpec,
)
from dr_graph.validation import validate_external_bindings

__all__ = [
    "BindingRef",
    "BindingSource",
    "ClassifiedFailure",
    "CompletedNodeError",
    "FieldRole",
    "FieldSpec",
    "GraphExecutionError",
    "GraphRunResult",
    "GraphRunStatus",
    "GraphSpec",
    "GraphValidationError",
    "InputResolutionError",
    "NodeConfig",
    "NodeError",
    "NodeExecutionError",
    "NodeOutcome",
    "NodeOutcomeStatus",
    "NodeOutput",
    "NodeSpec",
    "RunNode",
    "TerminalError",
    "as_binding_ref",
    "canonical_graph_payload",
    "execute_graph",
    "graph",
    "graph_digest",
    "inline_subgraph",
    "node",
    "resolve_node_inputs",
    "validate_external_bindings",
]
