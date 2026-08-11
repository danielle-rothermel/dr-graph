from __future__ import annotations

from typing import ClassVar


class GraphExecutionError(Exception):
    pass


class GraphValidationError(GraphExecutionError, ValueError):
    pass


class InputResolutionError(GraphExecutionError):
    failure_class: ClassVar[str] = "infrastructure"


class NodeExecutionError(GraphExecutionError):
    failure_class: ClassVar[str] = "infrastructure"


class CompletedNodeError(GraphExecutionError):
    pass
