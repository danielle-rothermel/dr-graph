from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

from dr_graph.core.fields import NodeFieldSpec  # noqa: TC001
from dr_graph.core.input_sources import NodeInputSourceRef  # noqa: TC001
from dr_graph.definitions.validation import validate_node_definition


class NodeDefinition(BaseModel):
    """Declares one Node's Definition, DAG wiring, and required Variables.

    ``variable_names`` are the declared Variables a Graph Config must set for
    this Node; ``input_sources`` fix the DAG shape and input contract;
    ``fields`` and ``output_field`` declare the input/output contract.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: StrictStr
    node_type: StrictStr = Field(min_length=1)
    fields: tuple[NodeFieldSpec, ...] = ()
    input_sources: dict[str, NodeInputSourceRef] = Field(default_factory=dict)
    output_field: StrictStr
    variable_names: frozenset[str] = frozenset()

    def dependencies(self) -> set[str]:
        return {
            node_id
            for ref in self.input_sources.values()
            if (node_id := ref.dependency_node_id) is not None
        }

    @model_validator(mode="after")
    def validate_definition(self) -> NodeDefinition:
        validate_node_definition(self)
        return self
