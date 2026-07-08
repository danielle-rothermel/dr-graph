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
    BindingRef,
    FieldRole,
    FieldSpec,
    GraphSpec,
    NodeConfig,
    NodeOutput,
    NodeSpec,
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
    bindings: dict[str, str] | None = None,
    output_field: str = "output",
) -> NodeSpec:
    input_bindings = {
        name: BindingRef.model_validate(ref)
        for name, ref in (bindings or {}).items()
    }
    fields = [
        FieldSpec(name=name, role=FieldRole.INPUT) for name in input_bindings
    ]
    fields.append(FieldSpec(name=output_field, role=FieldRole.OUTPUT))
    return NodeSpec(
        id=node_id,
        op="llm_call",
        config=NodeConfig(
            fields=tuple(fields),
            input_bindings=input_bindings,
            output_field=output_field,
        ),
    )


def _output(value: Any, *, field: str = "output") -> NodeOutput:
    return NodeOutput(values={field: value})


def _graph(
    *nodes: NodeSpec,
    terminal_node_id: str,
) -> GraphSpec:
    return GraphSpec(
        nodes=nodes,
        terminal_node_id=terminal_node_id,
    )
