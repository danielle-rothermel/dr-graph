"""Parameterized reserved external-input namespace (default "task")."""

from __future__ import annotations

import pytest

from dr_graph import (
    EXTERNAL_NAMESPACE_CONTEXT_KEY,
    BindingRef,
    BindingSource,
    GraphRunStatus,
    GraphSpec,
    execute_graph,
    external_namespaces,
    graph,
    graph_digest,
    node,
)

ENV_CONTEXT = {EXTERNAL_NAMESPACE_CONTEXT_KEY: "env"}


def _env_graph() -> GraphSpec:
    return graph(
        [
            node(
                "direct",
                op="llm_call",
                bindings={"prompt": "env.prompt"},
                output_field="output",
                external_namespace="env",
            ),
        ],
        terminal="direct",
        external_namespace="env",
    )


def test_default_namespace_parses_task_refs() -> None:
    ref = BindingRef.model_validate("task.prompt")
    assert ref.source is BindingSource.EXTERNAL
    assert ref.namespace == "task"
    assert ref.ref == "task.prompt"


def test_custom_namespace_parses_and_serializes() -> None:
    ref = BindingRef.model_validate("env.prompt", context=ENV_CONTEXT)
    assert ref.source is BindingSource.EXTERNAL
    assert ref.namespace == "env"
    assert ref.ref == "env.prompt"


def test_default_namespace_treats_other_heads_as_node_refs() -> None:
    ref = BindingRef.model_validate("env.prompt")
    assert ref.source is BindingSource.NODE
    assert ref.node_id == "env"
    assert ref.field == "prompt"


def test_custom_namespace_frees_task_as_node_id() -> None:
    ref = BindingRef.model_validate("task.output", context=ENV_CONTEXT)
    assert ref.source is BindingSource.NODE
    assert ref.node_id == "task"

    spec = graph(
        [
            node(
                "task",
                op="llm_call",
                bindings={"prompt": "env.prompt"},
                output_field="output",
                external_namespace="env",
            ),
        ],
        terminal="task",
        external_namespace="env",
    )
    assert spec.node("task").id == "task"


def test_custom_namespace_reserved_for_node_ids() -> None:
    with pytest.raises(ValueError, match=r"'env' is reserved"):
        node(
            "env",
            op="llm_call",
            output_field="output",
            external_namespace="env",
        )


def test_custom_namespace_round_trips_through_payload() -> None:
    spec = _env_graph()
    payload = spec.model_dump(mode="json")
    assert payload["nodes"][0]["config"]["input_bindings"]["prompt"] == (
        "env.prompt"
    )

    round_tripped = GraphSpec.model_validate(payload, context=ENV_CONTEXT)
    assert round_tripped == spec
    assert external_namespaces(round_tripped) == frozenset({"env"})


def test_namespace_is_digest_affecting() -> None:
    task_spec = graph(
        [
            node(
                "direct",
                op="llm_call",
                bindings={"prompt": "task.prompt"},
                output_field="output",
            ),
        ],
        terminal="direct",
    )
    assert graph_digest(task_spec) != graph_digest(_env_graph())


def test_custom_namespace_executes() -> None:
    result = execute_graph(
        graph=_env_graph(),
        inputs={"prompt": "write add"},
        run_node=lambda _node, inputs: {
            "values": {"output": f"code for {inputs['prompt']}"}
        },
    )
    assert result.status is GraphRunStatus.SUCCESS
    assert result.terminal_output == "code for write add"


def test_mixed_external_namespaces_rejected() -> None:
    task_node = node(
        "a",
        op="llm_call",
        bindings={"prompt": "task.prompt"},
        output_field="output",
    )
    env_node = node(
        "b",
        op="llm_call",
        bindings={"prompt": "env.prompt"},
        output_field="output",
        external_namespace="env",
    )
    with pytest.raises(ValueError, match="mixes external namespaces"):
        GraphSpec(nodes=(task_node, env_node), terminal_node_id="a")


def test_node_id_collision_with_used_namespace_rejected() -> None:
    # "env" is a legal node id under the default namespace, but a graph
    # whose refs use "env" as the external namespace cannot also name a
    # node "env" — the ref grammar would be ambiguous.
    env_ref_node = node(
        "a",
        op="llm_call",
        bindings={"prompt": "env.prompt"},
        output_field="output",
        external_namespace="env",
    )
    collider = node("env", op="llm_call", output_field="output")
    with pytest.raises(ValueError, match="collides with the external"):
        GraphSpec(nodes=(env_ref_node, collider), terminal_node_id="a")


def test_node_refs_reject_namespace_payloads() -> None:
    with pytest.raises(ValueError, match="cannot include namespace"):
        BindingRef.model_validate(
            {"source": "node", "node_id": "enc", "namespace": "task"}
        )
