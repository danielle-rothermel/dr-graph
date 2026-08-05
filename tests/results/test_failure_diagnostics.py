"""The structural ClassifiedFailure contract."""

from __future__ import annotations

from typing import Any

from dr_graph import ClassifiedFailure, NodeError
from tests.core.support import PermanentFailureError


class FullyClassifiedError(Exception):
    def __init__(self) -> None:
        super().__init__("boom")
        self.failure_class = "transient"
        self.error_type = "example.Boom"
        self.metadata: dict[str, Any] = {"attempt": 1}
        self.underlying: BaseException | None = ValueError("root")


def test_fully_conforming_exception_matches_protocol() -> None:
    assert isinstance(FullyClassifiedError(), ClassifiedFailure)


def test_node_error_reads_protocol_attributes() -> None:
    error = NodeError.from_exception(FullyClassifiedError())
    assert error.error_type == "example.Boom"
    assert error.failure_class == "transient"
    assert error.metadata == {
        "attempt": 1,
        "underlying_exception_type": "builtins.ValueError",
    }


def test_partial_conformance_is_tolerated() -> None:
    # Class-level StrEnum failure_class, no error_type attribute.
    error = NodeError.from_exception(
        PermanentFailureError("bad", metadata={"stage": "parse"})
    )
    assert error.failure_class == "permanent"
    assert error.error_type == "tests.core.support.PermanentFailureError"
    assert error.metadata == {"stage": "parse"}


def test_unclassified_exception_gets_defaults() -> None:
    error = NodeError.from_exception(ValueError("plain"))
    assert error.error_type == "builtins.ValueError"
    assert error.failure_class is None
    assert error.metadata == {}
