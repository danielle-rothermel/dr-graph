from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StrictStr

if TYPE_CHECKING:
    from collections.abc import Mapping


@runtime_checkable
class ClassifiedFailure(Protocol):
    """Structural contract for exceptions carrying failure diagnostics.

    ``NodeError.from_exception`` reads these attributes off any raised
    exception; partial conformance is tolerated (each attribute is
    consulted independently, with fallbacks). Canonical failure-class
    string values live with the raising layer, not here.
    """

    failure_class: str | None
    error_type: str
    metadata: Mapping[str, Any]
    underlying: BaseException | None


class NodeError(BaseModel):
    """Lightweight JSON-safe error snapshot for graph run summaries.

    Authoritative failure diagnostics belong on node-attempt records at the
    platform boundary, not in this runner-local shape.
    """

    model_config = ConfigDict(extra="forbid")

    error_type: StrictStr
    message: StrictStr
    failure_class: StrictStr | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_exception(cls, error: BaseException) -> NodeError:
        return cls(
            error_type=_exception_error_type(error),
            message=str(error),
            failure_class=_exception_failure_class(error),
            metadata=_exception_metadata(error),
        )


def _exception_failure_class(error: BaseException) -> str | None:
    failure_class = getattr(error, "failure_class", None)
    if isinstance(failure_class, StrEnum):
        return failure_class.value
    if isinstance(failure_class, str):
        return failure_class
    failure_class = getattr(type(error), "failure_class", None)
    if isinstance(failure_class, StrEnum):
        return failure_class.value
    if isinstance(failure_class, str):
        return failure_class
    return None


def _exception_error_type(error: BaseException) -> str:
    error_type = getattr(error, "error_type", None)
    if isinstance(error_type, str):
        return error_type
    return f"{type(error).__module__}.{type(error).__qualname__}"


def _exception_type_name(error: BaseException) -> str:
    return f"{type(error).__module__}.{type(error).__qualname__}"


def _root_exception(error: BaseException) -> BaseException:
    current = error
    while True:
        underlying = getattr(current, "underlying", None)
        if not isinstance(underlying, BaseException):
            return current
        current = underlying


def _exception_metadata(error: BaseException) -> dict[str, Any]:
    metadata = getattr(error, "metadata", None)
    result = dict(metadata) if isinstance(metadata, dict) else {}
    if getattr(error, "underlying", None) is not None:
        result.setdefault(
            "underlying_exception_type",
            _exception_type_name(_root_exception(error)),
        )
    return result
