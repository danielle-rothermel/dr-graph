"""Shared test doubles.

`PermanentFailureError` mirrors the shape of an app-side classified
failure: a class-level `StrEnum` failure class plus instance `underlying`
and `metadata` attributes, matching the `ClassifiedFailure` protocol the
runner introspects.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar

from dr_graph import (
    FieldRole,
    GraphConfig,
    NodeConfig,
    NodeFieldSpec,
    NodeInputSourceRef,
    NodeOutput,
)


class SupportFailureClass(StrEnum):
    PERMANENT = "permanent"


class PermanentFailureError(Exception):
    failure_class: ClassVar[SupportFailureClass] = (
        SupportFailureClass.PERMANENT
    )

    def __init__(
        self,
        message: str,
        *,
        underlying: BaseException | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.underlying = underlying
        self.metadata = dict(metadata or {})


def _node(
    node_id: str,
    *,
    input_sources: dict[str, str] | None = None,
    output_field: str = "output",
) -> NodeConfig:
    sources = {
        name: NodeInputSourceRef.model_validate(ref)
        for name, ref in (input_sources or {}).items()
    }
    fields = [
        NodeFieldSpec(name=name, role=FieldRole.INPUT) for name in sources
    ]
    fields.append(NodeFieldSpec(name=output_field, role=FieldRole.OUTPUT))
    return NodeConfig(
        node_id=node_id,
        node_type="llm_call",
        fields=tuple(fields),
        input_sources=sources,
        output_field=output_field,
    )


def _output(value: Any, *, field: str = "output") -> NodeOutput:
    return NodeOutput(values={field: value})


def _graph(
    *nodes: NodeConfig,
    terminal_node_id: str,
) -> GraphConfig:
    return GraphConfig(
        nodes=nodes,
        terminal_node_id=terminal_node_id,
    )
