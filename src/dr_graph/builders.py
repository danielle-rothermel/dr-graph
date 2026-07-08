"""Neutral spec-assembly helpers.

These cover the common case — bindings, one declared output field, open
parameters — without any prompt or provider awareness. Domain-aware builders
belong app-side.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

from dr_graph.models import (
    BindingRef,
    FieldRole,
    FieldSpec,
    GraphSpec,
    NodeConfig,
    NodeSpec,
)


def as_binding_ref(
    ref: str | BindingRef,
) -> BindingRef:
    if isinstance(ref, BindingRef):
        return ref
    return BindingRef.model_validate(ref)


def node(  # noqa: PLR0913 -- the spec surface, not incidental knobs
    node_id: str,
    *,
    op: str,
    output_field: str,
    bindings: Mapping[str, str | BindingRef] | None = None,
    fields: Sequence[FieldSpec] | None = None,
    parameters: Mapping[str, Any] | None = None,
) -> NodeSpec:
    input_bindings = {
        name: as_binding_ref(ref)
        for name, ref in (bindings or {}).items()
    }
    if fields is None:
        derived = [
            FieldSpec(name=name, role=FieldRole.INPUT)
            for name in input_bindings
        ]
        derived.append(FieldSpec(name=output_field, role=FieldRole.OUTPUT))
        field_specs = tuple(derived)
    else:
        field_specs = tuple(fields)
    return NodeSpec.model_validate(
        {
            "id": node_id,
            "op": op,
            "config": NodeConfig(
                fields=field_specs,
                input_bindings=input_bindings,
                output_field=output_field,
                parameters=dict(parameters or {}),
            ),
        }
    )


def graph(
    nodes: Sequence[NodeSpec],
    *,
    terminal: str,
) -> GraphSpec:
    return GraphSpec.model_validate(
        {
            "nodes": tuple(nodes),
            "terminal_node_id": terminal,
        }
    )
