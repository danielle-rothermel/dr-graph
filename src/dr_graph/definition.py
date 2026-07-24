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
    Field,
    StrictInt,
    StrictStr,
    model_validator,
)

from dr_graph.errors import GraphValidationError
from dr_graph.refs import NodeInputSourceRef, validate_ref_identifier
from dr_graph.spec import (
    GraphConfig,
    NodeConfig,
    NodeFieldSpec,
    validate_node_fields,
)
from dr_graph.validation import (
    topological_order_ids,
    validate_single_terminal_ids,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


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
        validate_ref_identifier(self.node_id, kind="node id")
        validate_node_fields(
            self.fields,
            self.input_sources,
            self.output_field,
        )
        return self


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
        if not self.nodes:
            raise GraphValidationError(
                "graph definition must have at least one node"
            )
        node_ids = self.node_ids()
        if len(node_ids) != len(set(node_ids)):
            raise GraphValidationError("duplicate node ids")
        known = set(node_ids)
        if self.terminal_node_id not in known:
            raise GraphValidationError(
                f"terminal_node_id {self.terminal_node_id!r} not in "
                "graph definition"
            )
        dependencies = {
            node.node_id: node.dependencies() for node in self.nodes
        }
        for node_id, deps in dependencies.items():
            unknown = sorted(deps - known)
            if unknown:
                joined = ", ".join(repr(dep) for dep in unknown)
                raise GraphValidationError(
                    f"node {node_id!r} depends on unknown node(s) {joined}"
                )
        # Enforce acyclicity and exactly one terminal/sink at Definition level.
        topological_order_ids(node_ids, dependencies)
        validate_single_terminal_ids(
            node_ids,
            dependencies,
            terminal_node_id=self.terminal_node_id,
        )
        return self

    def materialize(
        self,
        variable_assignments: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> GraphConfig:
        """Materialize one fully-set Graph Config.

        ``variable_assignments`` maps each ``node_id`` to that Node's concrete
        Variable values. Every declared Variable for every Node must be set.
        """
        assignments = variable_assignments or {}
        unknown = sorted(set(assignments) - set(self.node_ids()))
        if unknown:
            joined = ", ".join(repr(node_id) for node_id in unknown)
            raise ValueError(
                f"variable assignment(s) {joined} reference unknown node id(s)"
            )
        nodes: list[NodeConfig] = []
        for definition in self.nodes:
            values = dict(assignments.get(definition.node_id, {}))
            missing = sorted(definition.variable_names - set(values))
            if missing:
                joined = ", ".join(repr(name) for name in missing)
                raise ValueError(
                    f"node {definition.node_id!r} is missing required "
                    f"variable assignment(s) {joined}"
                )
            extra = sorted(set(values) - definition.variable_names)
            if extra:
                joined = ", ".join(repr(name) for name in extra)
                raise ValueError(
                    f"node {definition.node_id!r} sets undeclared "
                    f"variable(s) {joined}"
                )
            nodes.append(
                NodeConfig(
                    node_id=definition.node_id,
                    node_type=definition.node_type,
                    fields=definition.fields,
                    input_sources=dict(definition.input_sources),
                    output_field=definition.output_field,
                    variables=values,
                )
            )
        return GraphConfig(
            nodes=tuple(nodes),
            terminal_node_id=self.terminal_node_id,
        )
