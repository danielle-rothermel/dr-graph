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

from dr_graph.refs import BindingRef, validate_ref_identifier
from dr_graph.validation import topological_order, validate_graph_spec

DEFAULT_FIELD_TYPE = "str"


class FieldRole(StrEnum):
    INPUT = "input"
    OUTPUT = "output"


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    role: FieldRole
    type_name: StrictStr = Field(
        default=DEFAULT_FIELD_TYPE,
        min_length=1,
    )
    description: StrictStr | None = None


class NodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: tuple[FieldSpec, ...] = ()
    input_bindings: dict[str, BindingRef] = Field(default_factory=dict)
    output_field: StrictStr
    # Included in graph_digest via GraphSpec.model_dump; keep payloads small.
    parameters: dict[str, Any] = Field(default_factory=dict)

    def input_fields(self) -> tuple[FieldSpec, ...]:
        return tuple(
            field for field in self.fields if field.role is FieldRole.INPUT
        )

    def output_fields(self) -> tuple[FieldSpec, ...]:
        return tuple(
            field for field in self.fields if field.role is FieldRole.OUTPUT
        )

    @model_validator(mode="after")
    def validate_fields(self) -> NodeConfig:
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
        for field_name in self.input_bindings:
            if field_name not in input_names:
                raise ValueError(
                    f"input binding {field_name!r} is not an input field"
                )
        return self


class NodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrictStr
    config: NodeConfig
    op: StrictStr = Field(min_length=1)

    @model_validator(mode="after")
    def validate_id(self) -> NodeSpec:
        validate_ref_identifier(self.id, kind="node id")
        return self

    def dependencies(self) -> set[str]:
        return {
            node_id
            for ref in self.config.input_bindings.values()
            if (node_id := ref.dependency_node_id) is not None
        }


class GraphSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: tuple[NodeSpec, ...]
    terminal_node_id: StrictStr

    def node_ids(self) -> list[str]:
        return [node.id for node in self.nodes]

    def node(self, node_id: str) -> NodeSpec:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(node_id)

    def topological_order(self) -> tuple[NodeSpec, ...]:
        return topological_order(self.nodes)

    @model_validator(mode="after")
    def validate_graph(self) -> GraphSpec:
        validate_graph_spec(self)
        return self
