from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

from dr_graph.core.fields import FieldRole, NodeFieldSpec, validate_node_fields
from dr_graph.core.input_sources import (
    NodeInputSourceRef,
    validate_ref_identifier,
)


class NodeConfig(BaseModel):
    """Static node configuration included in its graph's identity.

    ``node_type`` is an opaque definition reference; the interpreter does not
    dispatch on it. Nodes are addressed by ``(graph_hash, node_id)`` rather
    than an independent identity hash.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: StrictStr
    node_type: StrictStr = Field(min_length=1)
    fields: tuple[NodeFieldSpec, ...] = ()
    input_sources: dict[str, NodeInputSourceRef] = Field(default_factory=dict)
    output_field: StrictStr
    variables: dict[str, Any] = Field(default_factory=dict)

    def input_fields(self) -> tuple[NodeFieldSpec, ...]:
        return tuple(
            field for field in self.fields if field.role is FieldRole.INPUT
        )

    def output_fields(self) -> tuple[NodeFieldSpec, ...]:
        return tuple(
            field for field in self.fields if field.role is FieldRole.OUTPUT
        )

    def dependencies(self) -> set[str]:
        return {
            node_id
            for ref in self.input_sources.values()
            if (node_id := ref.dependency_node_id) is not None
        }

    @model_validator(mode="after")
    def validate_node(self) -> NodeConfig:
        validate_ref_identifier(self.node_id, kind="node id")
        validate_node_fields(
            self.fields,
            self.input_sources,
            self.output_field,
        )
        return self
