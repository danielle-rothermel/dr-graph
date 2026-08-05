from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictStr,
    model_serializer,
    model_validator,
)

EXTERNAL_NAMESPACE = "task"
REF_SEPARATOR = "."


def validate_ref_identifier(
    identifier: str,
    *,
    kind: str,
) -> None:
    if REF_SEPARATOR in identifier:
        raise ValueError(
            f"{kind} {identifier!r} cannot contain {REF_SEPARATOR!r}"
        )
    if identifier == EXTERNAL_NAMESPACE:
        raise ValueError(f"{kind} {identifier!r} is reserved")


class NodeInputSourceKind(StrEnum):
    GRAPH_EXTERNAL = "graph_external"
    NODE_OUTPUT = "node_output"


class NodeInputSourceRef(BaseModel):
    """One Node Input Source.

    Maps one declared Node input to exactly one Graph External Input
    (``task.<field>``) or one upstream Node Output (``node_id`` or
    ``node_id.<field>``). Participates in Graph Config identity.
    """

    model_config = ConfigDict(extra="forbid")

    kind: NodeInputSourceKind
    field: StrictStr | None = None
    node_id: StrictStr | None = None

    @model_validator(mode="before")
    @classmethod
    def parse_ref(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        head, separator, tail = value.partition(REF_SEPARATOR)
        if not separator:
            return {
                "kind": NodeInputSourceKind.NODE_OUTPUT,
                "node_id": head,
            }
        if head == EXTERNAL_NAMESPACE:
            return {
                "kind": NodeInputSourceKind.GRAPH_EXTERNAL,
                "field": tail,
            }
        return {
            "kind": NodeInputSourceKind.NODE_OUTPUT,
            "node_id": head,
            "field": tail,
        }

    @model_validator(mode="after")
    def validate_shape(self) -> NodeInputSourceRef:
        if self.kind is NodeInputSourceKind.GRAPH_EXTERNAL:
            if self.node_id is not None:
                raise ValueError(
                    "graph external input sources cannot include node_id"
                )
            if not self.field:
                raise ValueError(
                    "graph external input sources require a field"
                )
            return self
        if not self.node_id:
            raise ValueError("node output input sources require node_id")
        validate_ref_identifier(self.node_id, kind="node id")
        if self.field is not None and not self.field:
            raise ValueError(
                "node output input sources require a non-empty field"
            )
        return self

    @model_serializer(mode="plain")
    def serialize_ref(self) -> str:
        return self.ref

    @property
    def ref(self) -> str:
        if self.kind is NodeInputSourceKind.GRAPH_EXTERNAL:
            return f"{EXTERNAL_NAMESPACE}{REF_SEPARATOR}{self.field}"
        if self.field is None:
            return str(self.node_id)
        return f"{self.node_id}{REF_SEPARATOR}{self.field}"

    @property
    def dependency_node_id(self) -> str | None:
        if self.kind is NodeInputSourceKind.NODE_OUTPUT:
            return self.node_id
        return None
