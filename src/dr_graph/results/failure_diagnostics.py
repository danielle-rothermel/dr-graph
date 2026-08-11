from __future__ import annotations

import traceback
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from dr_serialize import Jsonable, StrictJsonError
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from dr_graph.core.json_values import strict_json_object, strict_json_value

DROPPED_METADATA_KEY = "dropped_metadata"
DECLARED_ERROR_TYPE_KEY = "declared_error_type"

DROP_REASON_NON_STRING_KEY = "non_string_key"
DROP_REASON_STRICT_JSON = "strict_json"
DROP_REASON_METADATA_ACCESSOR_FAILED = "metadata_accessor_failed"
DROP_REASON_DECLARED_ERROR_TYPE_CONFLICT = "declared_error_type_conflict"


@runtime_checkable
class ClassifiedFailure(Protocol):
    """Diagnostic attributes recognized by ``NodeError.from_exception``.

    The extractor consults each attribute independently, so nonconforming
    exceptions may still provide a subset. Failure-class values are owned by
    the raising layer. A string ``error_type`` attribute is treated as a
    caller-declared label and is persisted in metadata, not as
    ``NodeError.error_type``.
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
    traceback: StrictStr = ""

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, value: Any) -> dict[str, Jsonable]:
        return strict_json_object(value)

    @classmethod
    def from_exception(cls, error: BaseException) -> NodeError:
        metadata = _exception_metadata(error)
        _apply_declared_error_type(error, metadata)
        return cls(
            error_type=_exception_error_type(error),
            message=_exception_message(error),
            failure_class=_exception_failure_class(error),
            metadata=metadata,
            traceback=_exception_traceback(error),
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
    return _exception_type_name(error)


def _exception_message(error: BaseException) -> str:
    try:
        return str(error)
    except Exception:  # noqa: BLE001 -- diagnostics must not mask node failures
        return _exception_type_name(error)


def _exception_type_name(error: BaseException) -> str:
    return f"{type(error).__module__}.{type(error).__qualname__}"


def _exception_traceback(error: BaseException) -> str:
    if error.__traceback__ is None:
        return ""
    return "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )


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


def _record_dropped_metadata(
    metadata: dict[str, Jsonable],
    *,
    key: Jsonable,
    reason: str,
) -> None:
    dropped = metadata.setdefault(DROPPED_METADATA_KEY, [])
    if not isinstance(dropped, list):
        return
    dropped.append({"key": key, "reason": reason})


def _apply_declared_error_type(
    error: BaseException,
    metadata: dict[str, Jsonable],
) -> None:
    declared_error_type = _exception_attribute(error, "error_type")
    if not isinstance(declared_error_type, str):
        return
    if DECLARED_ERROR_TYPE_KEY in metadata:
        _record_dropped_metadata(
            metadata,
            key=DECLARED_ERROR_TYPE_KEY,
            reason=DROP_REASON_DECLARED_ERROR_TYPE_CONFLICT,
        )
        return
    metadata[DECLARED_ERROR_TYPE_KEY] = declared_error_type


def _read_metadata(error: BaseException) -> tuple[object, bool]:
    try:
        metadata = getattr(error, "metadata", _MISSING_ATTRIBUTE)
    except Exception:  # noqa: BLE001 -- diagnostics must not mask node failures
        return _MISSING_ATTRIBUTE, True
    if metadata is _MISSING_ATTRIBUTE:
        return _MISSING_ATTRIBUTE, False
    return metadata, False


def _merge_dropped_metadata_lists(
    result: dict[str, Jsonable],
    existing: list[Jsonable],
) -> None:
    if not existing:
        return
    new_drops = result.get(DROPPED_METADATA_KEY)
    if isinstance(new_drops, list):
        result[DROPPED_METADATA_KEY] = [*existing, *new_drops]
        return
    result[DROPPED_METADATA_KEY] = existing


def _read_existing_dropped_metadata(
    metadata_attr: Mapping[Any, Any],
) -> tuple[list[Jsonable], bool]:
    if DROPPED_METADATA_KEY not in metadata_attr:
        return [], False
    try:
        validated = strict_json_value(metadata_attr[DROPPED_METADATA_KEY])
    except StrictJsonError:
        return [], True
    if isinstance(validated, list):
        return validated, False
    return [], True


def _exception_metadata(error: BaseException) -> dict[str, Jsonable]:
    metadata_attr, accessor_failed = _read_metadata(error)
    result: dict[str, Jsonable] = {}
    existing_dropped: list[Jsonable] = []
    if accessor_failed:
        _record_dropped_metadata(
            result,
            key="*",
            reason=DROP_REASON_METADATA_ACCESSOR_FAILED,
        )
    elif isinstance(metadata_attr, Mapping):
        existing_dropped, invalid_existing = _read_existing_dropped_metadata(
            metadata_attr,
        )
        if invalid_existing:
            _record_dropped_metadata(
                result,
                key=DROPPED_METADATA_KEY,
                reason=DROP_REASON_STRICT_JSON,
            )
        for key, value in metadata_attr.items():
            if key == DROPPED_METADATA_KEY:
                continue
            if not isinstance(key, str):
                try:
                    dropped_key = strict_json_value(key)
                except StrictJsonError:
                    dropped_key = str(key)
                _record_dropped_metadata(
                    result,
                    key=dropped_key,
                    reason=DROP_REASON_NON_STRING_KEY,
                )
                continue
            try:
                result[key] = strict_json_value(value)
            except StrictJsonError:
                _record_dropped_metadata(
                    result,
                    key=key,
                    reason=DROP_REASON_STRICT_JSON,
                )
        _merge_dropped_metadata_lists(result, existing_dropped)

    underlying = _exception_attribute(error, "underlying")
    if isinstance(underlying, BaseException):
        result.setdefault(
            "underlying_exception_type",
            _exception_type_name(_root_exception(error)),
        )
    return result
