from __future__ import annotations

from pydantic import BaseModel, ConfigDict, StrictStr, model_validator

from dr_graph.configuration.nodes import (
    NodeConfig,  # noqa: TC001 -- Pydantic runtime
)
from dr_graph.configuration.validation import (
    topological_order,
    validate_graph_config,
)


class GraphConfig(BaseModel):
    """Static graph whose identity document determines ``graph_hash``."""

    model_config = ConfigDict(extra="forbid")

    nodes: tuple[NodeConfig, ...]
    terminal_node_id: StrictStr

    def node_ids(self) -> list[str]:
        return [node.node_id for node in self.nodes]

    def node(self, node_id: str) -> NodeConfig:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(node_id)

    def topological_order(self) -> tuple[NodeConfig, ...]:
        return topological_order(self.nodes)

    @model_validator(mode="after")
    def validate_graph(self) -> GraphConfig:
        validate_graph_config(self)
        return self
