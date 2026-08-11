from __future__ import annotations

from typing import ClassVar

INFRASTRUCTURE_FAILURE_CLASS = "infrastructure"


class GraphExecutionError(Exception):
    pass


class GraphValidationError(GraphExecutionError, ValueError):
    pass


class InputResolutionError(GraphExecutionError):
    failure_class: ClassVar[str] = INFRASTRUCTURE_FAILURE_CLASS


class NodeExecutionError(GraphExecutionError):
    failure_class: ClassVar[str] = INFRASTRUCTURE_FAILURE_CLASS


class CompletedNodeError(GraphExecutionError):
    pass
