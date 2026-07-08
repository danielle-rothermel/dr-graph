from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    model_validator,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class NodeOutcomeStatus(StrEnum):
    """Runner outcome states, not append-only node-attempt row states.

    BLOCKED means the node was not invoked because an upstream dependency did
    not succeed. Persistence wrappers should not store BLOCKED as a node
    attempt outcome; it is derivable from the graph and upstream outcomes.
    """

    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"


class GraphRunStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"
    PARTIAL = "partial"


@runtime_checkable
class ClassifiedFailure(Protocol):
    """Structural contract for exceptions carrying failure diagnostics.

    ``NodeError.from_exception`` reads these attributes off any raised
    exception; partial conformance is tolerated (each attribute is
    consulted independently, with fallbacks). Canonical failure-class
    string values live with the raising layer, not here.
    """

    failure_class: str | None
    error_type: str
    metadata: Mapping[str, Any]
    underlying: BaseException | None


class NodeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class NodeError(BaseModel):
    """Lightweight JSON-safe error snapshot for graph run summaries.

    Authoritative failure diagnostics belong on node-attempt records at the
    platform boundary, not in this runner-local shape.
    """

    model_config = ConfigDict(extra="forbid")

    error_type: StrictStr
    message: StrictStr
    failure_class: StrictStr | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_exception(cls, error: BaseException) -> NodeError:
        return cls(
            error_type=_exception_error_type(error),
            message=str(error),
            failure_class=_exception_failure_class(error),
            metadata=_exception_metadata(error),
        )


class NodeOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: StrictStr
    status: NodeOutcomeStatus
    output: NodeOutput | None = None
    error: NodeError | None = None
    blocked_by: tuple[StrictStr, ...] = ()

    @classmethod
    def success(cls, *, node_id: str, output: NodeOutput) -> NodeOutcome:
        return cls(
            node_id=node_id,
            status=NodeOutcomeStatus.SUCCESS,
            output=output,
        )

    @classmethod
    def from_error(
        cls,
        *,
        node_id: str,
        error: BaseException,
    ) -> NodeOutcome:
        return cls(
            node_id=node_id,
            status=NodeOutcomeStatus.ERROR,
            error=NodeError.from_exception(error),
        )

    @classmethod
    def blocked(
        cls,
        *,
        node_id: str,
        blocked_by: tuple[str, ...],
    ) -> NodeOutcome:
        return cls(
            node_id=node_id,
            status=NodeOutcomeStatus.BLOCKED,
            blocked_by=blocked_by,
        )

    @model_validator(mode="after")
    def validate_outcome(self) -> NodeOutcome:
        if self.status is NodeOutcomeStatus.SUCCESS:
            if self.output is None:
                raise ValueError("successful node outcomes require output")
            if self.error is not None:
                raise ValueError(
                    "successful node outcomes cannot include error"
                )
            if self.blocked_by:
                raise ValueError(
                    "successful node outcomes cannot include blocked_by"
                )
            return self
        if self.status is NodeOutcomeStatus.ERROR:
            if self.error is None:
                raise ValueError("error node outcomes require error")
            if self.output is not None:
                raise ValueError("error node outcomes cannot include output")
            if self.blocked_by:
                raise ValueError(
                    "error node outcomes cannot include blocked_by"
                )
            return self
        if not self.blocked_by:
            raise ValueError("blocked node outcomes require blocked_by")
        if self.output is not None:
            raise ValueError("blocked node outcomes cannot include output")
        if self.error is not None:
            raise ValueError("blocked node outcomes cannot include error")
        return self


class TerminalError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: StrictStr
    status: NodeOutcomeStatus
    error: NodeError | None = None
    blocked_by: tuple[StrictStr, ...] = ()

    @model_validator(mode="after")
    def validate_terminal_error(self) -> TerminalError:
        if self.status is NodeOutcomeStatus.ERROR:
            if self.error is None:
                raise ValueError("error terminal outcomes require error")
            if self.blocked_by:
                raise ValueError(
                    "error terminal outcomes cannot include blocked_by"
                )
            return self
        if self.status is NodeOutcomeStatus.BLOCKED:
            if not self.blocked_by:
                raise ValueError(
                    "blocked terminal outcomes require blocked_by"
                )
            if self.error is not None:
                raise ValueError(
                    "blocked terminal outcomes cannot include error"
                )
            return self
        raise ValueError("terminal error status must be error or blocked")


class GraphRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: GraphRunStatus
    outcomes: dict[str, NodeOutcome]
    execution_order: tuple[StrictStr, ...]
    terminal_node_id: StrictStr
    terminal_output: Any | None = None
    terminal_error: TerminalError | None = None

    @model_validator(mode="after")
    def validate_result(self) -> GraphRunResult:
        for key, outcome in self.outcomes.items():
            if key != outcome.node_id:
                raise ValueError(
                    f"outcome key {key!r} does not match "
                    f"node_id {outcome.node_id!r}"
                )

        if (
            self.terminal_output is not None
            and self.terminal_error is not None
        ):
            raise ValueError(
                "graph run result cannot include both "
                "terminal_output and terminal_error"
            )

        if self.status in (GraphRunStatus.SUCCESS, GraphRunStatus.PARTIAL):
            if self.terminal_error is not None:
                raise ValueError(
                    f"{self.status.value} graph runs cannot include "
                    "terminal_error"
                )
            return self

        if self.terminal_error is None:
            raise ValueError(
                f"{self.status.value} graph runs require terminal_error"
            )
        if self.terminal_output is not None:
            raise ValueError(
                f"{self.status.value} graph runs cannot include "
                "terminal_output"
            )
        if self.terminal_error.node_id != self.terminal_node_id:
            raise ValueError(
                "terminal_error node_id must match terminal_node_id"
            )
        if self.status is GraphRunStatus.ERROR:
            if self.terminal_error.status is not NodeOutcomeStatus.ERROR:
                raise ValueError(
                    "terminal_error status must be error for error graph runs"
                )
            return self
        if self.terminal_error.status is not NodeOutcomeStatus.BLOCKED:
            raise ValueError(
                "terminal_error status must be blocked for blocked graph runs"
            )
        return self


def _exception_failure_class(error: BaseException) -> str | None:
    failure_class = getattr(error, "failure_class", None)
    if isinstance(failure_class, StrEnum):
        return failure_class.value
    if isinstance(failure_class, str):
        return failure_class
    failure_class = getattr(type(error), "failure_class", None)
    if isinstance(failure_class, StrEnum):
        return failure_class.value
    if isinstance(failure_class, str):
        return failure_class
    return None


def _exception_error_type(error: BaseException) -> str:
    error_type = getattr(error, "error_type", None)
    if isinstance(error_type, str):
        return error_type
    return f"{type(error).__module__}.{type(error).__qualname__}"


def _exception_type_name(error: BaseException) -> str:
    return f"{type(error).__module__}.{type(error).__qualname__}"


def _root_exception(error: BaseException) -> BaseException:
    current = error
    while True:
        underlying = getattr(current, "underlying", None)
        if not isinstance(underlying, BaseException):
            return current
        current = underlying


def _exception_metadata(error: BaseException) -> dict[str, Any]:
    metadata = getattr(error, "metadata", None)
    result = dict(metadata) if isinstance(metadata, dict) else {}
    if getattr(error, "underlying", None) is not None:
        result.setdefault(
            "underlying_exception_type",
            _exception_type_name(_root_exception(error)),
        )
    return result
