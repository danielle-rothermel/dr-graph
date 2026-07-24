"""Hashable computation-graph configs and a pure deterministic interpreter."""

from dr_graph.builders import as_node_input_source_ref, graph, node
from dr_graph.compose import inline_subgraph
from dr_graph.definition import GraphDefinition, NodeDefinition
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
    GRAPH_CONFIG_IDENTITY_SCHEMA,
    GRAPH_CONFIG_IDENTITY_SCHEMA_VERSION,
    graph_config_identity_document,
    graph_config_identity_payload,
    graph_hash,
)
from dr_graph.refs import (
    NodeInputSourceKind,
    NodeInputSourceRef,
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
    GraphConfig,
    NodeConfig,
    NodeFieldSpec,
)
from dr_graph.validation import validate_graph_external_inputs

__all__ = [
    "GRAPH_CONFIG_IDENTITY_SCHEMA",
    "GRAPH_CONFIG_IDENTITY_SCHEMA_VERSION",
    "ClassifiedFailure",
    "CompletedNodeError",
    "FieldRole",
    "GraphConfig",
    "GraphDefinition",
    "GraphExecutionError",
    "GraphRunResult",
    "GraphRunStatus",
    "GraphValidationError",
    "InputResolutionError",
    "NodeConfig",
    "NodeDefinition",
    "NodeError",
    "NodeExecutionError",
    "NodeFieldSpec",
    "NodeInputSourceKind",
    "NodeInputSourceRef",
    "NodeOutcome",
    "NodeOutcomeStatus",
    "NodeOutput",
    "RunNode",
    "TerminalError",
    "as_node_input_source_ref",
    "execute_graph",
    "graph",
    "graph_config_identity_document",
    "graph_config_identity_payload",
    "graph_hash",
    "inline_subgraph",
    "node",
    "resolve_node_inputs",
    "validate_graph_external_inputs",
]
