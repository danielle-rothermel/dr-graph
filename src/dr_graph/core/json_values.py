from __future__ import annotations

from typing import Any, cast

from dr_serialize import Jsonable, validate_strict_json


def strict_json_object(value: Any) -> dict[str, Jsonable]:
    """Validate and narrow an object-shaped strict JSON boundary."""
    return cast("dict[str, Jsonable]", validate_strict_json(value))


def strict_json_value(value: Any) -> Jsonable:
    """Validate and narrow a strict JSON boundary."""
    return validate_strict_json(value)
