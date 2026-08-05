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
from dr_graph.definitions.nodes import (
    NodeDefinition,  # noqa: TC001 -- Pydantic runtime
)
from dr_graph.definitions.validation import validate_graph_definition

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dr_graph.configuration.graphs import GraphConfig


class GraphDefinition(BaseModel):
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
        """Bind exactly the variables declared by each node."""
        return materialize_graph_definition(self, variable_assignments)
