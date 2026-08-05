from __future__ import annotations

import json
import subprocess
import sys
from collections import UserDict
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

import pytest

from dr_graph import (
    ClassifiedFailure,
    GraphRunResult,
    GraphRunStatus,
    NodeConfig,
    NodeError,
    NodeOutput,
    execute_graph,
)
from tests.support import PermanentFailureError, _graph, _node


class FullyClassifiedError(Exception):
    def __init__(self) -> None:
        super().__init__("boom")
        self.failure_class = "transient"
        self.error_type = "example.Boom"
        self.metadata: Mapping[str, Any] = {"attempt": 1}
        self.underlying: BaseException | None = ValueError("root")


def _execute_raising_node(error: BaseException) -> GraphRunResult:
    graph = _graph(_node("direct"), terminal_node_id="direct")

    def run_node(node: NodeConfig, inputs: Mapping[str, Any]) -> NodeOutput:
        raise error

    return execute_graph(graph=graph, inputs={}, run_node=run_node)


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
    error = NodeError.from_exception(
        PermanentFailureError("bad", metadata={"stage": "parse"})
    )
    assert error.failure_class == "permanent"
    assert error.error_type == "tests.support.PermanentFailureError"
    assert error.metadata == {"stage": "parse"}


def test_unclassified_exception_gets_defaults() -> None:
    error = NodeError.from_exception(ValueError("plain"))
    assert error.error_type == "builtins.ValueError"
    assert error.failure_class is None
    assert error.metadata == {}


@pytest.mark.parametrize(
    ("metadata", "underlying"),
    [
        pytest.param(
            MappingProxyType({"attempt": 1}),
            None,
            id="mapping-proxy-without-underlying",
        ),
        pytest.param(
            MappingProxyType({"attempt": 1}),
            ValueError("root"),
            id="mapping-proxy-with-underlying",
        ),
        pytest.param(
            UserDict({"attempt": 1}),
            None,
            id="user-dict-without-underlying",
        ),
        pytest.param(
            UserDict({"attempt": 1}),
            ValueError("root"),
            id="user-dict-with-underlying",
        ),
    ],
)
def test_node_error_preserves_mapping_metadata(
    metadata: Mapping[str, Any],
    underlying: BaseException | None,
) -> None:
    error = FullyClassifiedError()
    error.metadata = metadata
    error.underlying = underlying

    snapshot = NodeError.from_exception(error)

    expected = {"attempt": 1}
    if underlying is not None:
        expected["underlying_exception_type"] = "builtins.ValueError"
    assert snapshot.metadata == expected
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


def test_invalid_exception_metadata_does_not_escape_execution() -> None:
    class InvalidMetadataError(Exception):
        def __init__(self) -> None:
            super().__init__("callback failed")
            self.metadata = {"provider": "test", "opaque": object()}
            self.underlying = ValueError("invalid payload")

    result = _execute_raising_node(InvalidMetadataError())

    outcome = result.outcomes["direct"]
    assert result.status is GraphRunStatus.ERROR
    assert outcome.error is not None
    assert outcome.error.metadata == {
        "provider": "test",
        "underlying_exception_type": "builtins.ValueError",
    }


def test_node_error_preserves_wrapped_step_failure_diagnostics() -> None:
    class StepFailure(Exception):  # noqa: N818 -- mirrors a wrapped step failure
        def __init__(self) -> None:
            super().__init__("provider failed")
            self.error_type = "builtins.RuntimeError"
            self.failure_class = "permanent"
            self.metadata = {"provider": "test"}

    result = _execute_raising_node(StepFailure())

    outcome = result.outcomes["direct"]
    assert outcome.error is not None
    assert outcome.error.error_type == "builtins.RuntimeError"
    assert outcome.error.failure_class == "permanent"
    assert outcome.error.metadata == {"provider": "test"}
    assert result.terminal_error is not None
    assert result.terminal_error.error == outcome.error


def test_node_error_preserves_chained_underlying_exception_type() -> None:
    error = PermanentFailureError(
        "outer",
        underlying=PermanentFailureError(
            "middle",
            underlying=ValueError("inner"),
        ),
        metadata={"stage": "parse"},
    )

    result = _execute_raising_node(error)

    outcome = result.outcomes["direct"]
    assert outcome.error is not None
    assert outcome.error.metadata["underlying_exception_type"] == (
        "builtins.ValueError"
    )
