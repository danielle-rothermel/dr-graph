from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

from dr_graph.results.failure_diagnostics import NodeError  # noqa: TC001
from dr_graph.results.node_outcomes import NodeOutcome, NodeOutcomeStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dr_graph.configuration.graphs import GraphConfig


class GraphRunStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"
    PARTIAL = "partial"


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
    """Result for one Graph Run.

    Carries Graph Run identity (``graph_hash``), the Graph External Inputs or
    immutable references that fed the run, the terminal Outcome, per-Node
    Outcomes and execution order, provenance, and provider-attempt evidence as
    references only. It references — never duplicates — provider bodies held by
    the enclosing Rollout Result, holds no Platform Stage state, and has no
    separate authoritative persistence path.
    """

    model_config = ConfigDict(extra="forbid")

    graph_hash: StrictStr
    external_inputs: dict[str, Any] = Field(default_factory=dict)
    status: GraphRunStatus
    outcomes: dict[str, NodeOutcome]
    execution_order: tuple[StrictStr, ...]
    terminal_node_id: StrictStr
    terminal_output: Any | None = None
    terminal_error: TerminalError | None = None
    # Provider Call Attempt records live on the enclosing Rollout Result; the
    # Graph Run Result references them rather than duplicating provider bodies.
    attempt_evidence_refs: tuple[StrictStr, ...] = ()
    provenance: dict[str, Any] = Field(default_factory=dict)

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
        terminal_error = TerminalError(
            node_id=terminal.node_id,
            status=terminal.status,
            error=terminal.error,
            blocked_by=terminal.blocked_by,
        )

    return GraphRunResult(
        graph_hash=graph_hash_value,
        external_inputs=dict(inputs),
        status=_graph_status(
            terminal=terminal,
            outcomes=outcomes,
        ),
        outcomes=outcomes,
        execution_order=execution_order,
        terminal_node_id=graph.terminal_node_id,
        terminal_output=terminal_output,
        terminal_error=terminal_error,
    )


def _graph_status(
    *,
    terminal: NodeOutcome,
    outcomes: Mapping[str, NodeOutcome],
) -> GraphRunStatus:
    if terminal.status is not NodeOutcomeStatus.SUCCESS:
        if terminal.status is NodeOutcomeStatus.BLOCKED:
            return GraphRunStatus.BLOCKED
        return GraphRunStatus.ERROR
    if any(
        outcome.status is not NodeOutcomeStatus.SUCCESS
        for outcome in outcomes.values()
    ):
        return GraphRunStatus.PARTIAL
    return GraphRunStatus.SUCCESS
