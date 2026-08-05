from __future__ import annotations

from typing import TYPE_CHECKING

from dr_graph.assembly.builders import as_node_input_source_ref
from dr_graph.configuration.external_inputs import external_input_fields
from dr_graph.configuration.nodes import NodeConfig
from dr_graph.core.input_sources import (
    REF_SEPARATOR,
    NodeInputSourceKind,
    NodeInputSourceRef,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dr_graph.configuration.graphs import GraphConfig

DEFAULT_SUBGRAPH_SEPARATOR = ":"


def prefixed_node_id(
    prefix: str,
    node_id: str,
    *,
    separator: str = DEFAULT_SUBGRAPH_SEPARATOR,
) -> str:
    return f"{prefix}{separator}{node_id}"


def inline_subgraph(
    subgraph: GraphConfig,
    *,
    prefix: str,
    input_sources: Mapping[str, str | NodeInputSourceRef] | None = None,
    separator: str = DEFAULT_SUBGRAPH_SEPARATOR,
) -> tuple[NodeConfig, ...]:
    """Inline renamed nodes and remap selected external inputs.

    Unmapped external inputs remain external inputs of the parent graph.
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
        name: as_node_input_source_ref(ref)
        for name, ref in (input_sources or {}).items()
    }
    unknown = sorted(set(remapped) - external_input_fields(subgraph))
    if unknown:
        unknown_list = ", ".join(repr(name) for name in unknown)
        raise ValueError(
            f"input source(s) {unknown_list} are not external inputs "
            "of the subgraph"
        )
    nodes: list[NodeConfig] = []
    for node in subgraph.nodes:
        node_input_sources: dict[str, NodeInputSourceRef] = {}
        for field_name, ref in node.input_sources.items():
            if ref.kind is NodeInputSourceKind.GRAPH_EXTERNAL:
                if ref.field is not None and ref.field in remapped:
                    node_input_sources[field_name] = remapped[ref.field]
                else:
                    node_input_sources[field_name] = ref
                continue
            node_input_sources[field_name] = NodeInputSourceRef.model_validate(
                {
                    "kind": NodeInputSourceKind.NODE_OUTPUT,
                    "node_id": prefixed_node_id(
                        prefix,
                        str(ref.node_id),
                        separator=separator,
                    ),
                    "field": ref.field,
                }
            )
        nodes.append(
            NodeConfig.model_validate(
                {
                    "node_id": prefixed_node_id(
                        prefix,
                        node.node_id,
                        separator=separator,
                    ),
                    "node_type": node.node_type,
                    "fields": node.fields,
                    "input_sources": node_input_sources,
                    "output_field": node.output_field,
                    "variables": dict(node.variables),
                }
            )
        )
    return tuple(nodes)
