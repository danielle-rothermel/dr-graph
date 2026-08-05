from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from dr_serialize import Jsonable, StrictJsonError
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from dr_graph.core.json_values import strict_json_object, strict_json_value


@runtime_checkable
class ClassifiedFailure(Protocol):
    """Diagnostic attributes recognized by ``NodeError.from_exception``.

    The extractor consults each attribute independently, so nonconforming
    exceptions may still provide a subset. Failure-class values are owned by
    the raising layer.
    """

    failure_class: str | None
    error_type: str
    metadata: Mapping[str, Any]
    underlying: BaseException | None


class NodeError(BaseModel):
    """JSON-safe graph-run error snapshot.

    Fuller attempt evidence stays caller-owned.
    """

    model_config = ConfigDict(extra="forbid")

    error_type: StrictStr
    message: StrictStr
    failure_class: StrictStr | None = None
    metadata: dict[str, Jsonable] = Field(default_factory=dict)

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, value: Any) -> dict[str, Jsonable]:
        return strict_json_object(value)

    @classmethod
    def from_exception(cls, error: BaseException) -> NodeError:
        return cls(
            error_type=_exception_error_type(error),
            message=_exception_message(error),
            failure_class=_exception_failure_class(error),
            metadata=_exception_metadata(error),
        )


_MISSING_ATTRIBUTE = object()


def _exception_attribute(error: object, name: str) -> object:
    try:
        return getattr(error, name, _MISSING_ATTRIBUTE)
    except Exception:  # noqa: BLE001 -- diagnostics must not mask node failures
        return _MISSING_ATTRIBUTE


def _exception_failure_class(error: BaseException) -> str | None:
    failure_class = _exception_attribute(error, "failure_class")
    if isinstance(failure_class, StrEnum):
        return failure_class.value
    if isinstance(failure_class, str):
        return failure_class
    failure_class = _exception_attribute(type(error), "failure_class")
    if isinstance(failure_class, StrEnum):
        return failure_class.value
    if isinstance(failure_class, str):
        return failure_class
    return None


def _exception_error_type(error: BaseException) -> str:
    error_type = _exception_attribute(error, "error_type")
    if isinstance(error_type, str):
        return error_type
    return f"{type(error).__module__}.{type(error).__qualname__}"


def _exception_message(error: BaseException) -> str:
    try:
        return str(error)
    except Exception:  # noqa: BLE001 -- diagnostics must not mask node failures
        return _exception_type_name(error)


def _exception_type_name(error: BaseException) -> str:
    return f"{type(error).__module__}.{type(error).__qualname__}"


def _root_exception(error: BaseException) -> BaseException:
    current = error
    visited: set[int] = set()
    while True:
        visited.add(id(current))
        underlying = _exception_attribute(current, "underlying")
        if (
            not isinstance(underlying, BaseException)
            or id(underlying) in visited
        ):
            return current
        current = underlying


def _exception_metadata(error: BaseException) -> dict[str, Jsonable]:
    metadata = _exception_attribute(error, "metadata")
    result: dict[str, Jsonable] = {}
    if isinstance(metadata, Mapping):
        for key, value in metadata.items():
            if not isinstance(key, str):
                continue
            try:
                result[key] = strict_json_value(value)
            except StrictJsonError:
                continue
    underlying = _exception_attribute(error, "underlying")
    if isinstance(underlying, BaseException):
        result.setdefault(
            "underlying_exception_type",
            _exception_type_name(_root_exception(error)),
        )
    return result
