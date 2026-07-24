"""Neutral config-assembly helpers.

These cover the common case — node input sources, one declared output field,
open Variable assignments — without any prompt or provider awareness.
Domain-aware builders belong app-side.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

from dr_graph.refs import NodeInputSourceRef
from dr_graph.spec import FieldRole, GraphConfig, NodeConfig, NodeFieldSpec


def as_node_input_source_ref(
    ref: str | NodeInputSourceRef,
) -> NodeInputSourceRef:
    if isinstance(ref, NodeInputSourceRef):
        return ref
    return NodeInputSourceRef.model_validate(ref)


def node(  # noqa: PLR0913 -- the config surface, not incidental knobs
    node_id: str,
    *,
    node_type: str,
    output_field: str,
    input_sources: Mapping[str, str | NodeInputSourceRef] | None = None,
    fields: Sequence[NodeFieldSpec] | None = None,
    variables: Mapping[str, Any] | None = None,
) -> NodeConfig:
    sources = {
        name: as_node_input_source_ref(ref)
        for name, ref in (input_sources or {}).items()
    }
    if fields is None:
        derived = [
            NodeFieldSpec(name=name, role=FieldRole.INPUT) for name in sources
        ]
        derived.append(NodeFieldSpec(name=output_field, role=FieldRole.OUTPUT))
        field_specs = tuple(derived)
    else:
        field_specs = tuple(fields)
    return NodeConfig.model_validate(
        {
            "node_id": node_id,
            "node_type": node_type,
            "fields": field_specs,
            "input_sources": sources,
            "output_field": output_field,
            "variables": dict(variables or {}),
        }
    )


def graph(
    nodes: Sequence[NodeConfig],
    *,
    terminal: str,
) -> GraphConfig:
    return GraphConfig.model_validate(
        {
            "nodes": tuple(nodes),
            "terminal_node_id": terminal,
        }
    )
