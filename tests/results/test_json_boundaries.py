from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from dr_serialize import StrictJsonError
from pydantic import BaseModel

from dr_graph import (
    GraphRunResult,
    GraphRunStatus,
    NodeError,
    NodeOutcome,
    NodeOutput,
)

type BoundaryFactory = Callable[[object], BaseModel]


def _result(**changes: Any) -> GraphRunResult:
    output = NodeOutput(values={"output": "ok"})
    fields: dict[str, Any] = {
        "graph_hash": "0" * 64,
        "external_inputs": {},
        "status": GraphRunStatus.SUCCESS,
        "outcomes": {
            "direct": NodeOutcome.success(node_id="direct", output=output)
        },
        "execution_order": ("direct",),
        "terminal_node_id": "direct",
        "terminal_output": "ok",
        "provenance": {},
    }
    fields.update(changes)
    return GraphRunResult(**fields)


BOUNDARIES: tuple[tuple[str, BoundaryFactory], ...] = (
    (
        "node-output-values",
        lambda value: NodeOutput(values={"payload": value}),
    ),
    (
        "node-output-metadata",
        lambda value: NodeOutput(values={}, metadata={"payload": value}),
    ),
    (
        "node-error-metadata",
        lambda value: NodeError(
            error_type="example.Error",
            message="failed",
            metadata={"payload": value},
        ),
    ),
    (
        "graph-external-inputs",
        lambda value: _result(external_inputs={"payload": value}),
    ),
    (
        "graph-terminal-output",
        lambda value: _result(terminal_output=value),
    ),
    (
        "graph-provenance",
        lambda value: _result(provenance={"payload": value}),
    ),
)

INVALID_JSON_VALUES = (
    pytest.param(object(), id="opaque-object"),
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="positive-infinity"),
    pytest.param(float("-inf"), id="negative-infinity"),
    pytest.param((1, 2), id="tuple"),
    pytest.param({1, 2}, id="set"),
    pytest.param({1: "value"}, id="non-string-key"),
    pytest.param({"nested": [object()]}, id="nested-opaque-object"),
)


@pytest.mark.parametrize(
    ("_boundary_name", "factory"),
    [pytest.param(name, factory, id=name) for name, factory in BOUNDARIES],
)
@pytest.mark.parametrize("invalid_value", INVALID_JSON_VALUES)
def test_result_boundaries_reject_non_json_values(
    _boundary_name: str,
    factory: BoundaryFactory,
    invalid_value: object,
) -> None:
    with pytest.raises(StrictJsonError):
        factory(invalid_value)


def test_valid_nested_json_round_trips_without_normalization() -> None:
    value = {
        "nested": [None, True, 1, 1.5, "text", {"key": "value"}],
    }
    result = _result(
        external_inputs={"input": value},
        terminal_output=value,
        provenance={"trace": value},
    )

    dumped = json.loads(result.model_dump_json())

    assert dumped["external_inputs"] == {"input": value}
    assert dumped["terminal_output"] == value
    assert dumped["provenance"] == {"trace": value}
