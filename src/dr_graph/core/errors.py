from __future__ import annotations


class GraphExecutionError(Exception):
    """Base exception for pure graph execution errors."""


class GraphValidationError(GraphExecutionError, ValueError):
    pass


class InputResolutionError(GraphExecutionError):
    pass


class NodeExecutionError(GraphExecutionError):
    pass


class CompletedNodeError(GraphExecutionError):
    """Raised when a supplied completed-node output cannot be used."""
