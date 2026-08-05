from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, StrictStr

if TYPE_CHECKING:
    from collections.abc import Collection

    from dr_graph.core.input_sources import NodeInputSourceRef

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


def validate_node_fields(
    fields: tuple[NodeFieldSpec, ...],
    input_sources: dict[str, NodeInputSourceRef],
    output_field: str,
) -> None:
    """Enforce a Node's field/source contract.

    Shared by ``NodeConfig`` and ``NodeDefinition``: requires at least one
    field, unique field names, ``output_field`` naming a declared OUTPUT
    field, and a bidirectional match between declared INPUT fields and
    ``input_sources`` keys.
    """
    if not fields:
        raise ValueError("node config must declare at least one field")

    field_names = [field.name for field in fields]
    if len(field_names) != len(set(field_names)):
        raise ValueError("duplicate field names in node config")

    output_names = {
        field.name for field in fields if field.role is FieldRole.OUTPUT
    }
    if output_field not in output_names:
        raise ValueError(
            f"output_field {output_field!r} is not an output field"
        )

    input_names = {
        field.name for field in fields if field.role is FieldRole.INPUT
    }
    for field_name in input_sources:
        if field_name not in input_names:
            raise ValueError(
                f"input source {field_name!r} is not an input field"
            )

    missing = sorted(input_names - set(input_sources))
    if missing:
        joined = ", ".join(repr(name) for name in missing)
        raise ValueError(f"input field(s) {joined} have no input source")


def missing_output_fields(
    fields: tuple[NodeFieldSpec, ...],
    available_fields: Collection[str],
) -> tuple[str, ...]:
    """Return declared output fields absent from one node output."""
    return tuple(
        sorted(
            field.name
            for field in fields
            if field.role is FieldRole.OUTPUT
            and field.name not in available_fields
        )
    )
