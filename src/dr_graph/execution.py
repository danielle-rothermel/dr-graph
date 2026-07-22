from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pydantic import ValidationError

from dr_graph.errors import (
    CompletedNodeError,
    InputResolutionError,
    NodeExecutionError,
)
from dr_graph.hashing import graph_hash
from dr_graph.refs import NodeInputSourceKind
from dr_graph.results import (
    GraphRunResult,
    GraphRunStatus,
    NodeOutcome,
    NodeOutcomeStatus,
    NodeOutput,
    TerminalError,
)
from dr_graph.spec import GraphConfig, NodeConfig

type RunNode = Callable[
    [NodeConfig, Mapping[str, Any]],
    NodeOutput | Mapping[str, Any],
]


def execute_graph(
    *,
    graph: GraphConfig,
    inputs: Mapping[str, Any],
    run_node: RunNode,
    completed: Mapping[str, NodeOutput | Mapping[str, Any]] | None = None,
) -> GraphRunResult:
    completed_outputs = _validated_completed_outputs(
        graph=graph,
        completed=completed,
    )
    outcomes: dict[str, NodeOutcome] = {}
    execution_order: list[str] = []

    for node in graph.topological_order():
        execution_order.append(node.node_id)
        if node.node_id in completed_outputs:
            outcomes[node.node_id] = NodeOutcome.success(
                node_id=node.node_id,
                output=completed_outputs[node.node_id],
            )
            continue
        blocked_by = _blocked_dependencies(node, outcomes)
        if blocked_by:
            outcomes[node.node_id] = NodeOutcome.blocked(
                node_id=node.node_id,
                blocked_by=blocked_by,
            )
            continue

        try:
            node_inputs = resolve_node_inputs(
                node=node,
                inputs=inputs,
                outcomes=outcomes,
                graph=graph,
            )
            output = _run_node(
                node=node,
                node_inputs=node_inputs,
                run_node=run_node,
            )
        except Exception as error:  # noqa: BLE001 -- outcomes absorb node failures
            outcomes[node.node_id] = NodeOutcome.from_error(
                node_id=node.node_id,
                error=error,
            )
            continue

        outcomes[node.node_id] = NodeOutcome.success(
            node_id=node.node_id,
            output=output,
        )

    return _build_result(
        graph=graph,
        outcomes=outcomes,
        execution_order=tuple(execution_order),
        inputs=inputs,
    )


def resolve_node_inputs(
    *,
    node: NodeConfig,
    inputs: Mapping[str, Any],
    outcomes: Mapping[str, NodeOutcome],
    graph: GraphConfig,
) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for field_name, ref in node.input_sources.items():
        if ref.kind is NodeInputSourceKind.GRAPH_EXTERNAL:
            if ref.field is None or ref.field not in inputs:
                raise InputResolutionError(
                    f"missing external input {ref.field!r} "
                    f"for node {node.node_id!r}"
                )
            resolved[field_name] = inputs[ref.field]
            continue

        if ref.node_id is None:
            raise InputResolutionError(
                f"node input source {ref.ref!r} has no node id"
            )
        upstream = outcomes.get(ref.node_id)
        if (
            upstream is None
            or upstream.status is not NodeOutcomeStatus.SUCCESS
        ):
            raise InputResolutionError(
                f"upstream node {ref.node_id!r} did not succeed"
            )
        if upstream.output is None:
            raise InputResolutionError(
                f"upstream node {ref.node_id!r} has no output"
            )
        output_field = ref.field or graph.node(ref.node_id).output_field
        if output_field not in upstream.output.values:
            raise InputResolutionError(
                f"upstream node {ref.node_id!r} output missing "
                f"field {output_field!r}"
            )
        resolved[field_name] = upstream.output.values[output_field]
    return resolved


def _validated_completed_outputs(
    *,
    graph: GraphConfig,
    completed: Mapping[str, NodeOutput | Mapping[str, Any]] | None,
) -> dict[str, NodeOutput]:
    if not completed:
        return {}
    node_ids = set(graph.node_ids())
    outputs: dict[str, NodeOutput] = {}
    for node_id, raw_output in completed.items():
        if node_id not in node_ids:
            raise CompletedNodeError(
                f"completed node {node_id!r} is not in the graph"
            )
        try:
            output = NodeOutput.model_validate(raw_output)
        except ValidationError as error:
            raise CompletedNodeError(
                f"completed output for node {node_id!r} is invalid: {error}"
            ) from error
        output_field = graph.node(node_id).output_field
        if output_field not in output.values:
            raise CompletedNodeError(
                f"completed output for node {node_id!r} missing "
                f"field {output_field!r}"
            )
        outputs[node_id] = output
    return outputs


def _run_node(
    *,
    node: NodeConfig,
    node_inputs: Mapping[str, Any],
    run_node: RunNode,
) -> NodeOutput:
    output = NodeOutput.model_validate(run_node(node, node_inputs))
    if node.output_field not in output.values:
        raise NodeExecutionError(
            f"node {node.node_id!r} output missing field "
            f"{node.output_field!r}"
        )
    return output


def _blocked_dependencies(
    node: NodeConfig,
    outcomes: Mapping[str, NodeOutcome],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            dependency
            for dependency in node.dependencies()
            if outcomes[dependency].status is not NodeOutcomeStatus.SUCCESS
        )
    )


def _build_result(
    *,
    graph: GraphConfig,
    outcomes: dict[str, NodeOutcome],
    execution_order: tuple[str, ...],
    inputs: Mapping[str, Any],
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
        graph_hash=graph_hash(graph),
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
