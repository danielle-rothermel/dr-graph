from __future__ import annotations

from typing import TYPE_CHECKING

from dr_graph.core.errors import GraphValidationError

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping


def validate_single_terminal_ids(
    node_ids: Collection[str],
    dependencies: Mapping[str, Collection[str]],
    *,
    terminal_node_id: str,
) -> None:
    consumed = {dep for deps in dependencies.values() for dep in deps}
    if terminal_node_id in consumed:
        raise GraphValidationError(
            f"terminal node {terminal_node_id!r} is consumed by another "
            "node and cannot be the sink"
        )
    other_sinks = sorted(
        node_id
        for node_id in node_ids
        if node_id not in consumed and node_id != terminal_node_id
    )
    if other_sinks:
        joined = ", ".join(repr(node_id) for node_id in other_sinks)
        raise GraphValidationError(
            f"graph has more than one terminal/sink node: "
            f"{terminal_node_id!r} and {joined}"
        )


def topological_order_ids(
    node_ids: Collection[str],
    dependencies: Mapping[str, Collection[str]],
) -> tuple[str, ...]:
    done: set[str] = set()
    remaining = set(node_ids)
    ordered: list[str] = []
    while remaining:
        ready = sorted(
            node_id
            for node_id in remaining
            if set(dependencies.get(node_id, ())) <= done
        )
        if not ready:
            stuck = ", ".join(sorted(remaining))
            raise GraphValidationError(f"graph has a cycle among: {stuck}")
        ordered.extend(ready)
        done.update(ready)
        remaining.difference_update(ready)
    return tuple(ordered)
