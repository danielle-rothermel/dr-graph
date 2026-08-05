"""The structural ClassifiedFailure contract."""

from __future__ import annotations

import json
import subprocess
import sys
from collections import UserDict
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

import pytest

from dr_graph import ClassifiedFailure, NodeError
from tests.core.support import PermanentFailureError


class FullyClassifiedError(Exception):
    def __init__(self) -> None:
        super().__init__("boom")
        self.failure_class = "transient"
        self.error_type = "example.Boom"
        self.metadata: Mapping[str, Any] = {"attempt": 1}
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


@pytest.mark.parametrize(
    "metadata",
    [
        pytest.param(
            MappingProxyType({"attempt": 1}),
            id="mapping-proxy",
        ),
        pytest.param(UserDict({"attempt": 1}), id="user-dict"),
    ],
)
def test_node_error_preserves_mapping_metadata(
    metadata: Mapping[str, Any],
) -> None:
    error = FullyClassifiedError()
    error.metadata = metadata

    snapshot = NodeError.from_exception(error)

    assert snapshot.metadata == {
        "attempt": 1,
        "underlying_exception_type": "builtins.ValueError",
    }
    assert dict(metadata) == {"attempt": 1}


@pytest.mark.parametrize(
    ("cycle_setup", "underlying_type"),
    [
        pytest.param(
            "outer.underlying = outer",
            "builtins.RuntimeError",
            id="self-cycle",
        ),
        pytest.param(
            "inner = ValueError('inner')\n"
            "inner.underlying = outer\n"
            "outer.underlying = inner",
            "builtins.ValueError",
            id="two-exception-cycle",
        ),
    ],
)
def test_node_error_underlying_cycle_terminates(
    cycle_setup: str,
    underlying_type: str,
) -> None:
    script = "\n".join(
        [
            "from dr_graph import NodeError",
            "outer = RuntimeError('outer')",
            *cycle_setup.splitlines(),
            "print(NodeError.from_exception(outer).model_dump_json())",
        ]
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "error_type": "builtins.RuntimeError",
        "message": "outer",
        "failure_class": None,
        "metadata": {"underlying_exception_type": underlying_type},
    }
