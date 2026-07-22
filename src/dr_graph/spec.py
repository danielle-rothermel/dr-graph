from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    model_validator,
)

from dr_graph.refs import NodeInputSourceRef, validate_ref_identifier
from dr_graph.validation import topological_order, validate_graph_config

DEFAULT_FIELD_TYPE = "str"


class FieldRole(StrEnum):
    INPUT = "input"
    OUTPUT = "output"


class NodeFieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    role: FieldRole
    type_name: StrictStr = Field(
        default=DEFAULT_FIELD_TYPE,
        min_length=1,
    )
    description: StrictStr | None = None


class NodeConfig(BaseModel):
    """Concrete Node (Config): the umbrella Node lifecycle role.

    Carries the node's identity (``node_id``), its Node Definition reference
    (``node_type``, an open string the interpreter never dispatches on),
    declared fields, one Node Input Source per declared runtime input,
    declared output field, and its static Variable assignments. Every field
    participates in ``graph_hash``; there is no separate Node Config hash.
    Addressed exactly as ``(graph_hash, node_id)``.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: StrictStr
    node_type: StrictStr = Field(min_length=1)
    fields: tuple[NodeFieldSpec, ...] = ()
    input_sources: dict[str, NodeInputSourceRef] = Field(default_factory=dict)
    output_field: StrictStr
    # Included in graph_hash via GraphConfig identity payload; keep small.
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

        if not self.fields:
            raise ValueError("node config must declare at least one field")

        field_names = [field.name for field in self.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError("duplicate field names in node config")

        output_names = {field.name for field in self.output_fields()}
        if self.output_field not in output_names:
            raise ValueError(
                f"output_field {self.output_field!r} is not an output field"
            )

        input_names = {field.name for field in self.input_fields()}
        for field_name in self.input_sources:
            if field_name not in input_names:
                raise ValueError(
                    f"input source {field_name!r} is not an input field"
                )
        return self


class GraphConfig(BaseModel):
    """Fully set concrete Graph Config: the sole Rollout Variant config.

    Its exact versioned Identity Document produces ``graph_hash``.
    """

    model_config = ConfigDict(extra="forbid")

    nodes: tuple[NodeConfig, ...]
    terminal_node_id: StrictStr

    def node_ids(self) -> list[str]:
        return [node.node_id for node in self.nodes]

    def node(self, node_id: str) -> NodeConfig:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(node_id)

    def topological_order(self) -> tuple[NodeConfig, ...]:
        return topological_order(self.nodes)

    @model_validator(mode="after")
    def validate_graph(self) -> GraphConfig:
        validate_graph_config(self)
        return self
