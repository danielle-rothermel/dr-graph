from __future__ import annotations

from typing import Any

import pytest

from dr_graph import NodeError, NodeOutcome, NodeOutcomeStatus
from tests.support import _output, failure_state_cases


def _node_error() -> NodeError:
    return NodeError(error_type="test", message="failed")


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        (
            {"node_id": "n", "status": NodeOutcomeStatus.SUCCESS},
            "require output",
        ),
        (
            {
                "node_id": "n",
                "status": NodeOutcomeStatus.SUCCESS,
                "output": _output("ok"),
                "error": _node_error(),
            },
            "cannot include error",
        ),
        (
            {
                "node_id": "n",
                "status": NodeOutcomeStatus.SUCCESS,
                "output": _output("ok"),
                "blocked_by": ("upstream",),
            },
            "cannot include blocked_by",
        ),
        (
            {
                "node_id": "n",
                "status": NodeOutcomeStatus.ERROR,
                "error": _node_error(),
                "output": _output("ok"),
            },
            "cannot include output",
        ),
        (
            {
                "node_id": "n",
                "status": NodeOutcomeStatus.BLOCKED,
                "blocked_by": ("upstream",),
                "output": _output("ok"),
            },
            "cannot include output",
        ),
        *[
            pytest.param(kwargs, match, id=case_id)
            for case_id, kwargs, match in failure_state_cases()
        ],
    ],
)
def test_node_outcome_rejects_invalid_field_combinations(
    kwargs: dict[str, Any],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        NodeOutcome(**kwargs)
