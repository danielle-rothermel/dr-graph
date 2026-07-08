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


class BindingSource(StrEnum):
    EXTERNAL = "external"
    NODE = "node"


class BindingRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: BindingSource
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
                "source": BindingSource.NODE,
                "node_id": head,
            }
        if head == EXTERNAL_NAMESPACE:
            return {
                "source": BindingSource.EXTERNAL,
                "field": tail,
            }
        return {
            "source": BindingSource.NODE,
            "node_id": head,
            "field": tail,
        }

    @model_validator(mode="after")
    def validate_shape(self) -> BindingRef:
        if self.source is BindingSource.EXTERNAL:
            if self.node_id is not None:
                raise ValueError(
                    "external binding refs cannot include node_id"
                )
            if not self.field:
                raise ValueError("external binding refs require a field")
            return self
        if not self.node_id:
            raise ValueError("node binding refs require node_id")
        validate_ref_identifier(self.node_id, kind="node id")
        if self.field is not None and not self.field:
            raise ValueError("node binding refs require a non-empty field")
        return self

    @model_serializer(mode="plain")
    def serialize_ref(self) -> str:
        return self.ref

    @property
    def ref(self) -> str:
        if self.source is BindingSource.EXTERNAL:
            return f"{EXTERNAL_NAMESPACE}{REF_SEPARATOR}{self.field}"
        if self.field is None:
            return str(self.node_id)
        return f"{self.node_id}{REF_SEPARATOR}{self.field}"

    @property
    def dependency_node_id(self) -> str | None:
        if self.source is BindingSource.NODE:
            return self.node_id
        return None
