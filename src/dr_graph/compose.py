"""Inline subgraph composition.

v1 represents composition by flattening: `inline_subgraph` returns the
subgraph's nodes renamed under a prefix, with internal refs rewired and
external inputs optionally rebound to parent-side refs. The composed
graph is an ordinary `GraphSpec`; its digest is the digest of the
flattened spec.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dr_graph.builders import as_binding_ref
from dr_graph.models import (
    REF_SEPARATOR,
    BindingRef,
    BindingSource,
    GraphSpec,
    NodeConfig,
    NodeSpec,
    external_binding_fields,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

DEFAULT_SUBGRAPH_SEPARATOR = ":"


def prefixed_node_id(
    prefix: str,
    node_id: str,
    *,
    separator: str = DEFAULT_SUBGRAPH_SEPARATOR,
) -> str:
    return f"{prefix}{separator}{node_id}"


def inline_subgraph(
    subgraph: GraphSpec,
    *,
    prefix: str,
    bindings: Mapping[str, str | BindingRef] | None = None,
    separator: str = DEFAULT_SUBGRAPH_SEPARATOR,
) -> tuple[NodeSpec, ...]:
    """Return the subgraph's nodes renamed and rewired for a parent graph.

    ``bindings`` maps external input fields of the subgraph to parent-side
    refs (parent node outputs or parent external inputs). Unmapped external
    inputs pass through unchanged and must be satisfied by the parent
    graph's external inputs.
    """
    if not prefix:
        raise ValueError("prefix must be non-empty")
    if REF_SEPARATOR in prefix:
        raise ValueError(f"prefix {prefix!r} cannot contain {REF_SEPARATOR!r}")
    if not separator or REF_SEPARATOR in separator:
        raise ValueError(
            f"separator {separator!r} must be non-empty and cannot "
            f"contain {REF_SEPARATOR!r}"
        )
    remapped = {
        name: as_binding_ref(ref)
        for name, ref in (bindings or {}).items()
    }
    unknown = sorted(set(remapped) - external_binding_fields(subgraph))
    if unknown:
        unknown_list = ", ".join(repr(name) for name in unknown)
        raise ValueError(
            f"binding(s) {unknown_list} are not external inputs "
            "of the subgraph"
        )
    nodes: list[NodeSpec] = []
    for node in subgraph.nodes:
        input_bindings: dict[str, BindingRef] = {}
        for field_name, ref in node.config.input_bindings.items():
            if ref.source is BindingSource.EXTERNAL:
                if ref.field is not None and ref.field in remapped:
                    input_bindings[field_name] = remapped[ref.field]
                else:
                    input_bindings[field_name] = ref
                continue
            input_bindings[field_name] = BindingRef.model_validate(
                {
                    "source": BindingSource.NODE,
                    "node_id": prefixed_node_id(
                        prefix,
                        str(ref.node_id),
                        separator=separator,
                    ),
                    "field": ref.field,
                }
            )
        nodes.append(
            NodeSpec.model_validate(
                {
                    "id": prefixed_node_id(
                        prefix,
                        node.id,
                        separator=separator,
                    ),
                    "op": node.op,
                    "config": NodeConfig(
                        fields=node.config.fields,
                        input_bindings=input_bindings,
                        output_field=node.config.output_field,
                        parameters=dict(node.config.parameters),
                        metadata=dict(node.config.metadata),
                    ),
                }
            )
        )
    return tuple(nodes)
