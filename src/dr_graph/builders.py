"""Neutral spec-assembly helpers.

These cover the common case — bindings, one declared output field, open
metadata — without any prompt or provider awareness. Domain-aware builders
belong app-side.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

from dr_graph.models import (
    DEFAULT_EXTERNAL_NAMESPACE,
    EXTERNAL_NAMESPACE_CONTEXT_KEY,
    BindingRef,
    FieldRole,
    FieldSpec,
    GraphSpec,
    NodeConfig,
    NodeSpec,
)


def as_binding_ref(
    ref: str | BindingRef,
    *,
    external_namespace: str = DEFAULT_EXTERNAL_NAMESPACE,
) -> BindingRef:
    if isinstance(ref, BindingRef):
        return ref
    return BindingRef.model_validate(
        ref,
        context={EXTERNAL_NAMESPACE_CONTEXT_KEY: external_namespace},
    )


def node(  # noqa: PLR0913 -- the spec surface, not incidental knobs
    node_id: str,
    *,
    op: str,
    output_field: str,
    bindings: Mapping[str, str | BindingRef] | None = None,
    fields: Sequence[FieldSpec] | None = None,
    parameters: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    external_namespace: str = DEFAULT_EXTERNAL_NAMESPACE,
) -> NodeSpec:
    input_bindings = {
        name: as_binding_ref(ref, external_namespace=external_namespace)
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
                metadata=dict(metadata or {}),
            ),
        },
        context={EXTERNAL_NAMESPACE_CONTEXT_KEY: external_namespace},
    )


def graph(
    nodes: Sequence[NodeSpec],
    *,
    terminal: str,
    external_namespace: str = DEFAULT_EXTERNAL_NAMESPACE,
) -> GraphSpec:
    return GraphSpec.model_validate(
        {
            "nodes": tuple(nodes),
            "terminal_node_id": terminal,
        },
        context={EXTERNAL_NAMESPACE_CONTEXT_KEY: external_namespace},
    )
