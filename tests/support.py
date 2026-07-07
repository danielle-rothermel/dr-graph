"""Shared test doubles.

`PermanentFailureError` mirrors the shape of an app-side classified
failure: a class-level `StrEnum` failure class plus instance `underlying`
and `metadata` attributes, matching the `ClassifiedFailure` protocol the
runner introspects.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar


class SupportFailureClass(StrEnum):
    PERMANENT = "permanent"


class PermanentFailureError(Exception):
    failure_class: ClassVar[SupportFailureClass] = (
        SupportFailureClass.PERMANENT
    )

    def __init__(
        self,
        message: str,
        *,
        underlying: BaseException | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.underlying = underlying
        self.metadata = dict(metadata or {})
