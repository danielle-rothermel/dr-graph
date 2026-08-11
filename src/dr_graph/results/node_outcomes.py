from __future__ import annotations

from enum import StrEnum
from typing import Any

from dr_serialize import Jsonable  # noqa: TC002 -- Pydantic runtime
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from dr_graph.core.json_values import strict_json_object
from dr_graph.results.failure_diagnostics import NodeError


class NodeOutcomeStatus(StrEnum):
    """Graph-run node states, including nodes blocked by dependencies."""

    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class NodeOutcomeSource(StrEnum):
    """Whether a successful node outcome came from this run or reuse."""

    FRESH = "fresh"
    REUSED = "reused"


class NodeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: dict[str, Jsonable]
    metadata: dict[str, Jsonable] = Field(default_factory=dict)

    @field_validator("values", "metadata", mode="before")
    @classmethod
    def validate_json_objects(cls, value: Any) -> dict[str, Jsonable]:
        return strict_json_object(value)


class NodeOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: StrictStr
    status: NodeOutcomeStatus
    output: NodeOutput | None = None
    error: NodeError | None = None
    blocked_by: tuple[StrictStr, ...] = ()
    outcome_source: NodeOutcomeSource = NodeOutcomeSource.FRESH

    @classmethod
    def success(
        cls,
        *,
        node_id: str,
        output: NodeOutput,
        outcome_source: NodeOutcomeSource = NodeOutcomeSource.FRESH,
    ) -> NodeOutcome:
        return cls(
            node_id=node_id,
            status=NodeOutcomeStatus.SUCCESS,
            output=output,
            outcome_source=outcome_source,
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

    @classmethod
    def cancelled(cls, *, node_id: str) -> NodeOutcome:
        return cls(
            node_id=node_id,
            status=NodeOutcomeStatus.CANCELLED,
        )

    @model_validator(mode="after")
    def validate_outcome(self) -> NodeOutcome:  # noqa: PLR0912
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
        if self.status is NodeOutcomeStatus.CANCELLED:
            if self.output is not None:
                raise ValueError(
                    "cancelled node outcomes cannot include output"
                )
            if self.error is not None:
                raise ValueError(
                    "cancelled node outcomes cannot include error"
                )
            if self.blocked_by:
                raise ValueError(
                    "cancelled node outcomes cannot include blocked_by"
                )
            return self
        if not self.blocked_by:
            raise ValueError("blocked node outcomes require blocked_by")
        if self.output is not None:
            raise ValueError("blocked node outcomes cannot include output")
        if self.error is not None:
            raise ValueError("blocked node outcomes cannot include error")
        return self
