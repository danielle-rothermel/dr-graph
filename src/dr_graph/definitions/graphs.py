"""Versioned, variable-bearing Graph Definition artifact.

A Graph Definition declares the Node Definitions, Variables, DAG shape,
input/output contracts, and exactly one terminal Node. It materializes one
or more fully-set Graph Configs by binding concrete Variable assignments to
each declared Node.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictInt,
    StrictStr,
    model_validator,
)

from dr_graph.definitions.materialization import materialize_graph_definition
from dr_graph.definitions.nodes import NodeDefinition  # noqa: TC001
from dr_graph.definitions.validation import validate_graph_definition

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dr_graph.configuration.graphs import GraphConfig


class GraphDefinition(BaseModel):
    """Versioned, variable-bearing DAG shape materializing Graph Configs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: StrictInt = 1
    nodes: tuple[NodeDefinition, ...]
    terminal_node_id: StrictStr

    def node_ids(self) -> list[str]:
        return [node.node_id for node in self.nodes]

    @model_validator(mode="after")
    def validate_definition(self) -> GraphDefinition:
        validate_graph_definition(self)
        return self

    def materialize(
        self,
        variable_assignments: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> GraphConfig:
        """Materialize one fully-set Graph Config.

        ``variable_assignments`` maps each ``node_id`` to that Node's concrete
        Variable values. Every declared Variable for every Node must be set.
        """
        return materialize_graph_definition(self, variable_assignments)
