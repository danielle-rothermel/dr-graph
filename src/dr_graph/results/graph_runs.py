from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from dr_serialize import Jsonable  # noqa: TC002 -- Pydantic runtime
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from dr_graph.core.json_values import strict_json_object, strict_json_value
from dr_graph.results.failure_diagnostics import (  # noqa: TC001 -- Pydantic runtime
    NodeError,
)
from dr_graph.results.node_outcomes import NodeOutcome, NodeOutcomeStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dr_graph.configuration.graphs import GraphConfig


class GraphRunStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TerminalError(BaseModel):
    """Represents an errored or dependency-blocked terminal node."""

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
        if self.status is NodeOutcomeStatus.CANCELLED:
            if self.error is not None:
                raise ValueError(
                    "cancelled terminal outcomes cannot include error"
                )
            if self.blocked_by:
                raise ValueError(
                    "cancelled terminal outcomes cannot include blocked_by"
                )
            return self
        raise ValueError(
            "terminal error status must be error, blocked, or cancelled"
        )


class GraphRunResult(BaseModel):
    """Graph-complete result of one graph run."""

    model_config = ConfigDict(extra="forbid")

    graph_hash: StrictStr
    external_inputs: dict[str, Jsonable] = Field(default_factory=dict)
    status: GraphRunStatus
    outcomes: dict[str, NodeOutcome]
    execution_order: tuple[StrictStr, ...]
    terminal_node_id: StrictStr
    terminal_output: Jsonable = None
    terminal_error: TerminalError | None = None

    @field_validator("external_inputs", mode="before")
    @classmethod
    def validate_json_objects(cls, value: Any) -> dict[str, Jsonable]:
        return strict_json_object(value)

    @field_validator("terminal_output", mode="before")
    @classmethod
    def validate_terminal_output(cls, value: Any) -> Jsonable:
        return strict_json_value(value)

    @model_validator(mode="after")
    def validate_result(self) -> GraphRunResult:
        _validate_terminal_fields(self)
        _validate_outcome_membership(self)
        _validate_outcome_coherence(self)
        return self


def _validate_terminal_fields(result: GraphRunResult) -> None:
    if (
        result.terminal_output is not None
        and result.terminal_error is not None
    ):
        raise ValueError(
            "graph run result cannot include both "
            "terminal_output and terminal_error"
        )
    if result.status is GraphRunStatus.SUCCESS:
        if result.terminal_error is not None:
            raise ValueError(
                "success graph runs cannot include terminal_error"
            )
        return
    if result.terminal_error is None:
        raise ValueError(
            f"{result.status.value} graph runs require terminal_error"
        )
    if result.terminal_output is not None:
        raise ValueError(
            f"{result.status.value} graph runs cannot include terminal_output"
        )
    if result.terminal_error.node_id != result.terminal_node_id:
        raise ValueError("terminal_error node_id must match terminal_node_id")
    if result.status is GraphRunStatus.ERROR:
        if result.terminal_error.status is not NodeOutcomeStatus.ERROR:
            raise ValueError(
                "terminal_error status must be error for error graph runs"
            )
        return
    if result.status is GraphRunStatus.CANCELLED:
        if result.terminal_error.status is not NodeOutcomeStatus.CANCELLED:
            raise ValueError(
                "terminal_error status must be cancelled "
                "for cancelled graph runs"
            )
        return
    if result.terminal_error.status is not NodeOutcomeStatus.BLOCKED:
        raise ValueError(
            "terminal_error status must be blocked for blocked graph runs"
        )


def _validate_outcome_membership(result: GraphRunResult) -> None:
    if not result.outcomes:
        raise ValueError("graph run result requires at least one outcome")
    for key, outcome in result.outcomes.items():
        if key != outcome.node_id:
            raise ValueError(
                f"outcome key {key!r} does not match "
                f"node_id {outcome.node_id!r}"
            )
    if result.terminal_node_id not in result.outcomes:
        raise ValueError(
            "terminal_node_id must identify an outcome in outcomes"
        )
    if len(result.execution_order) != len(result.outcomes) or set(
        result.execution_order
    ) != set(result.outcomes):
        raise ValueError(
            "execution_order must contain every outcome node exactly once"
        )


def _validate_outcome_coherence(result: GraphRunResult) -> None:
    terminal = result.outcomes[result.terminal_node_id]
    expected_status = _graph_status(terminal=terminal)
    if result.status is not expected_status:
        raise ValueError("graph run status must match terminal outcome")
    if result.status is GraphRunStatus.SUCCESS:
        if any(
            outcome.status is not NodeOutcomeStatus.SUCCESS
            for outcome in result.outcomes.values()
        ):
            raise ValueError(
                "successful graph runs require every outcome to succeed"
            )
        return
    expected_terminal_error = _terminal_error_from_outcome(terminal)
    if result.terminal_error != expected_terminal_error:
        raise ValueError("terminal_error must match terminal outcome")


def build_graph_run_result(
    *,
    graph: GraphConfig,
    outcomes: dict[str, NodeOutcome],
    execution_order: tuple[str, ...],
    inputs: Mapping[str, Any],
    graph_hash_value: str,
) -> GraphRunResult:
    terminal = outcomes[graph.terminal_node_id]
    terminal_output: Any | None = None
    terminal_error: TerminalError | None = None

    if terminal.status is NodeOutcomeStatus.SUCCESS:
        if terminal.output is not None:
            terminal_output = terminal.output.values[
                graph.node(graph.terminal_node_id).output_field
            ]
    else:
        terminal_error = _terminal_error_from_outcome(terminal)

    return GraphRunResult(
        graph_hash=graph_hash_value,
        external_inputs=dict(inputs),
        status=_graph_status(terminal=terminal),
        outcomes=outcomes,
        execution_order=execution_order,
        terminal_node_id=graph.terminal_node_id,
        terminal_output=terminal_output,
        terminal_error=terminal_error,
    )


def _graph_status(
    *,
    terminal: NodeOutcome,
) -> GraphRunStatus:
    if terminal.status is NodeOutcomeStatus.SUCCESS:
        return GraphRunStatus.SUCCESS
    if terminal.status is NodeOutcomeStatus.BLOCKED:
        return GraphRunStatus.BLOCKED
    if terminal.status is NodeOutcomeStatus.CANCELLED:
        return GraphRunStatus.CANCELLED
    return GraphRunStatus.ERROR


def _terminal_error_from_outcome(terminal: NodeOutcome) -> TerminalError:
    return TerminalError(
        node_id=terminal.node_id,
        status=terminal.status,
        error=terminal.error,
        blocked_by=terminal.blocked_by,
    )
