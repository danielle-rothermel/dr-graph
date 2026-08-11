from __future__ import annotations

from typing import TYPE_CHECKING

from dr_graph.core.errors import GraphExecutionError

if TYPE_CHECKING:
    from dr_graph.results.graph_runs import GraphRunResult


class GraphRunInterruptedError(GraphExecutionError):
    """Graph run interrupted after recording partial evidence."""

    def __init__(
        self,
        message: str,
        *,
        partial_result: GraphRunResult,
    ) -> None:
        super().__init__(message)
        self.partial_result = partial_result
