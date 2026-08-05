from __future__ import annotations


class GraphExecutionError(Exception):
    pass


class GraphValidationError(GraphExecutionError, ValueError):
    pass


class InputResolutionError(GraphExecutionError):
    pass


class NodeExecutionError(GraphExecutionError):
    pass


class CompletedNodeError(GraphExecutionError):
    pass
