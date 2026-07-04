from __future__ import annotations

from collections.abc import Collection, Mapping
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationInfo,
    model_serializer,
    model_validator,
)

DEFAULT_EXTERNAL_NAMESPACE = "task"
REF_SEPARATOR = "."
DEFAULT_FIELD_TYPE = "str"

EXTERNAL_NAMESPACE_CONTEXT_KEY = "external_namespace"


def context_external_namespace(info: ValidationInfo) -> str:
    """Resolve the reserved external-input namespace for a validation run.

    Pass ``context={"external_namespace": ...}`` to ``model_validate`` to
    parse specs written against a namespace other than the default
    ``"task"``. The namespace is digest-affecting: it appears in the
    serialized ref strings.
    """
    context = info.context
    if isinstance(context, Mapping):
        namespace = context.get(EXTERNAL_NAMESPACE_CONTEXT_KEY)
        if isinstance(namespace, str) and namespace:
            return namespace
    return DEFAULT_EXTERNAL_NAMESPACE


def validate_ref_identifier(
    identifier: str,
    *,
    kind: str,
    reserved: str = DEFAULT_EXTERNAL_NAMESPACE,
) -> None:
    if REF_SEPARATOR in identifier:
        raise ValueError(
            f"{kind} {identifier!r} cannot contain {REF_SEPARATOR!r}"
        )
    if identifier == reserved:
        raise ValueError(f"{kind} {identifier!r} is reserved")


class FieldRole(StrEnum):
    INPUT = "input"
    OUTPUT = "output"


class BindingSource(StrEnum):
    EXTERNAL = "external"
    NODE = "node"


class NodeOutcomeStatus(StrEnum):
    """Runner outcome states, not append-only node-attempt row states.

    BLOCKED means the node was not invoked because an upstream dependency did
    not succeed. Persistence wrappers should not store BLOCKED as a node
    attempt outcome; it is derivable from the graph and upstream outcomes.
    """

    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"


class GraphRunStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"
    PARTIAL = "partial"


@runtime_checkable
class ClassifiedFailure(Protocol):
    """Structural contract for exceptions carrying failure diagnostics.

    ``NodeError.from_exception`` reads these attributes off any raised
    exception; partial conformance is tolerated (each attribute is
    consulted independently, with fallbacks). Canonical failure-class
    string values live with the raising layer, not here.
    """

    failure_class: str | None
    error_type: str
    metadata: Mapping[str, Any]
    underlying: BaseException | None


class BindingRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: BindingSource
    field: StrictStr | None = None
    node_id: StrictStr | None = None
    namespace: StrictStr | None = None

    @model_validator(mode="before")
    @classmethod
    def parse_ref(cls, value: Any, info: ValidationInfo) -> Any:
        if not isinstance(value, str):
            return value
        namespace = context_external_namespace(info)
        head, separator, tail = value.partition(REF_SEPARATOR)
        if not separator:
            return {
                "source": BindingSource.NODE,
                "node_id": head,
            }
        if head == namespace:
            return {
                "source": BindingSource.EXTERNAL,
                "field": tail,
                "namespace": namespace,
            }
        return {
            "source": BindingSource.NODE,
            "node_id": head,
            "field": tail,
        }

    @model_validator(mode="after")
    def validate_shape(self, info: ValidationInfo) -> BindingRef:
        if self.source is BindingSource.EXTERNAL:
            if self.node_id is not None:
                raise ValueError(
                    "external binding refs cannot include node_id"
                )
            if not self.field:
                raise ValueError("external binding refs require a field")
            if self.namespace is None:
                self.namespace = context_external_namespace(info)
            if not self.namespace:
                raise ValueError(
                    "external binding refs require a non-empty namespace"
                )
            if REF_SEPARATOR in self.namespace:
                raise ValueError(
                    f"namespace {self.namespace!r} cannot contain "
                    f"{REF_SEPARATOR!r}"
                )
            return self
        if self.namespace is not None:
            raise ValueError("node binding refs cannot include namespace")
        if not self.node_id:
            raise ValueError("node binding refs require node_id")
        validate_ref_identifier(
            self.node_id,
            kind="node id",
            reserved=context_external_namespace(info),
        )
        if self.field is not None and not self.field:
            raise ValueError("node binding refs require a non-empty field")
        return self

    @model_serializer(mode="plain")
    def serialize_ref(self) -> str:
        return self.ref

    @property
    def ref(self) -> str:
        if self.source is BindingSource.EXTERNAL:
            return f"{self.namespace}{REF_SEPARATOR}{self.field}"
        if self.field is None:
            return str(self.node_id)
        return f"{self.node_id}{REF_SEPARATOR}{self.field}"

    @property
    def dependency_node_id(self) -> str | None:
        if self.source is BindingSource.NODE:
            return self.node_id
        return None


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    role: FieldRole
    type_name: StrictStr = Field(
        default=DEFAULT_FIELD_TYPE,
        min_length=1,
    )
    description: StrictStr | None = None


class NodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: tuple[FieldSpec, ...] = ()
    input_bindings: dict[str, BindingRef] = Field(default_factory=dict)
    output_field: StrictStr
    # Included in graph_digest via GraphSpec.model_dump; keep payloads small
    # until schema freeze adds explicit size/type constraints.
    parameters: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def input_fields(self) -> tuple[FieldSpec, ...]:
        return tuple(
            field for field in self.fields if field.role is FieldRole.INPUT
        )

    def output_fields(self) -> tuple[FieldSpec, ...]:
        return tuple(
            field for field in self.fields if field.role is FieldRole.OUTPUT
        )

    @model_validator(mode="after")
    def validate_fields(self) -> NodeConfig:
        if not self.fields:
            raise ValueError("node config must declare at least one field")

        field_names = [field.name for field in self.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError("duplicate field names in node config")

        output_names = {field.name for field in self.output_fields()}
        if self.output_field not in output_names:
            raise ValueError(
                f"output_field {self.output_field!r} is not an output field"
            )

        input_names = {field.name for field in self.input_fields()}
        for field_name in self.input_bindings:
            if field_name not in input_names:
                raise ValueError(
                    f"input binding {field_name!r} is not an input field"
                )
        return self


class NodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrictStr
    config: NodeConfig
    op: StrictStr = Field(min_length=1)

    @model_validator(mode="after")
    def validate_id(self, info: ValidationInfo) -> NodeSpec:
        validate_ref_identifier(
            self.id,
            kind="node id",
            reserved=context_external_namespace(info),
        )
        return self

    def dependencies(self) -> set[str]:
        return {
            node_id
            for ref in self.config.input_bindings.values()
            if (node_id := ref.dependency_node_id) is not None
        }


class GraphSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: tuple[NodeSpec, ...]
    terminal_node_id: StrictStr

    def node_ids(self) -> list[str]:
        return [node.id for node in self.nodes]

    def node(self, node_id: str) -> NodeSpec:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(node_id)

    def topological_order(self) -> tuple[NodeSpec, ...]:
        return topological_order(self.nodes)

    @model_validator(mode="after")
    def validate_graph(self) -> GraphSpec:
        validate_graph_spec(self)
        return self


class NodeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class NodeError(BaseModel):
    """Lightweight JSON-safe error snapshot for graph run summaries.

    Authoritative failure diagnostics belong on node-attempt records at the
    platform boundary, not in this runner-local shape.
    """

    model_config = ConfigDict(extra="forbid")

    error_type: StrictStr
    message: StrictStr
    failure_class: StrictStr | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_exception(cls, error: BaseException) -> NodeError:
        return cls(
            error_type=_exception_error_type(error),
            message=str(error),
            failure_class=_exception_failure_class(error),
            metadata=_exception_metadata(error),
        )


class NodeOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: StrictStr
    status: NodeOutcomeStatus
    output: NodeOutput | None = None
    error: NodeError | None = None
    blocked_by: tuple[StrictStr, ...] = ()

    @classmethod
    def success(cls, *, node_id: str, output: NodeOutput) -> NodeOutcome:
        return cls(
            node_id=node_id,
            status=NodeOutcomeStatus.SUCCESS,
            output=output,
        )

    @classmethod
    def from_error(
        cls,
        *,
        node_id: str,
        error: BaseException,
    ) -> NodeOutcome:
        return cls(
            node_id=node_id,
            status=NodeOutcomeStatus.ERROR,
            error=NodeError.from_exception(error),
        )

    @classmethod
    def blocked(
        cls,
        *,
        node_id: str,
        blocked_by: tuple[str, ...],
    ) -> NodeOutcome:
        return cls(
            node_id=node_id,
            status=NodeOutcomeStatus.BLOCKED,
            blocked_by=blocked_by,
        )

    @model_validator(mode="after")
    def validate_outcome(self) -> NodeOutcome:
        if self.status is NodeOutcomeStatus.SUCCESS:
            if self.output is None:
                raise ValueError("successful node outcomes require output")
            if self.error is not None:
                raise ValueError(
                    "successful node outcomes cannot include error"
                )
            if self.blocked_by:
                raise ValueError(
                    "successful node outcomes cannot include blocked_by"
                )
            return self
        if self.status is NodeOutcomeStatus.ERROR:
            if self.error is None:
                raise ValueError("error node outcomes require error")
            if self.output is not None:
                raise ValueError("error node outcomes cannot include output")
            if self.blocked_by:
                raise ValueError(
                    "error node outcomes cannot include blocked_by"
                )
            return self
        if not self.blocked_by:
            raise ValueError("blocked node outcomes require blocked_by")
        if self.output is not None:
            raise ValueError("blocked node outcomes cannot include output")
        if self.error is not None:
            raise ValueError("blocked node outcomes cannot include error")
        return self


class TerminalError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: StrictStr
    status: NodeOutcomeStatus
    error: NodeError | None = None
    blocked_by: tuple[StrictStr, ...] = ()

    @model_validator(mode="after")
    def validate_terminal_error(self) -> TerminalError:
        if self.status is NodeOutcomeStatus.ERROR:
            if self.error is None:
                raise ValueError("error terminal outcomes require error")
            if self.blocked_by:
                raise ValueError(
                    "error terminal outcomes cannot include blocked_by"
                )
            return self
        if self.status is NodeOutcomeStatus.BLOCKED:
            if not self.blocked_by:
                raise ValueError(
                    "blocked terminal outcomes require blocked_by"
                )
            if self.error is not None:
                raise ValueError(
                    "blocked terminal outcomes cannot include error"
                )
            return self
        raise ValueError("terminal error status must be error or blocked")


class GraphRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: GraphRunStatus
    outcomes: dict[str, NodeOutcome]
    execution_order: tuple[StrictStr, ...]
    terminal_node_id: StrictStr
    terminal_output: Any | None = None
    terminal_error: TerminalError | None = None

    @model_validator(mode="after")
    def validate_result(self) -> GraphRunResult:
        for key, outcome in self.outcomes.items():
            if key != outcome.node_id:
                raise ValueError(
                    f"outcome key {key!r} does not match "
                    f"node_id {outcome.node_id!r}"
                )

        if (
            self.terminal_output is not None
            and self.terminal_error is not None
        ):
            raise ValueError(
                "graph run result cannot include both "
                "terminal_output and terminal_error"
            )

        if self.status in (GraphRunStatus.SUCCESS, GraphRunStatus.PARTIAL):
            if self.terminal_error is not None:
                raise ValueError(
                    f"{self.status.value} graph runs cannot include "
                    "terminal_error"
                )
            return self

        if self.terminal_error is None:
            raise ValueError(
                f"{self.status.value} graph runs require terminal_error"
            )
        if self.terminal_output is not None:
            raise ValueError(
                f"{self.status.value} graph runs cannot include "
                "terminal_output"
            )
        if self.terminal_error.node_id != self.terminal_node_id:
            raise ValueError(
                "terminal_error node_id must match terminal_node_id"
            )
        if self.status is GraphRunStatus.ERROR:
            if self.terminal_error.status is not NodeOutcomeStatus.ERROR:
                raise ValueError(
                    "terminal_error status must be error for error graph runs"
                )
            return self
        if self.terminal_error.status is not NodeOutcomeStatus.BLOCKED:
            raise ValueError(
                "terminal_error status must be blocked for blocked graph runs"
            )
        return self


class GraphExecutionError(Exception):
    """Base exception for pure graph execution errors."""


class GraphValidationError(GraphExecutionError, ValueError):
    pass


class InputResolutionError(GraphExecutionError):
    pass


class NodeExecutionError(GraphExecutionError):
    pass


class CompletedNodeError(GraphExecutionError):
    """Raised when a supplied completed-node output cannot be used."""


def validate_graph_spec(graph: GraphSpec) -> None:
    if not graph.nodes:
        raise GraphValidationError("graph must have at least one node")
    node_ids = graph.node_ids()
    if len(node_ids) != len(set(node_ids)):
        raise GraphValidationError("duplicate node ids")
    nodes_by_id = {node.id: node for node in graph.nodes}
    if graph.terminal_node_id not in nodes_by_id:
        raise GraphValidationError(
            f"terminal_node_id {graph.terminal_node_id!r} not in graph"
        )
    for node in graph.nodes:
        for ref in node.config.input_bindings.values():
            validate_binding_ref(ref, nodes_by_id)
    namespaces = external_namespaces(graph)
    if len(namespaces) > 1:
        namespace_list = ", ".join(repr(name) for name in sorted(namespaces))
        raise GraphValidationError(
            f"graph mixes external namespaces: {namespace_list}"
        )
    for namespace in namespaces:
        if namespace in nodes_by_id:
            raise GraphValidationError(
                f"node id {namespace!r} collides with the external namespace"
            )
    validate_acyclic_graph(graph.nodes)


def external_namespaces(graph: GraphSpec) -> frozenset[str]:
    return frozenset(
        ref.namespace
        for node in graph.nodes
        for ref in node.config.input_bindings.values()
        if ref.source is BindingSource.EXTERNAL and ref.namespace is not None
    )


def external_binding_fields(graph: GraphSpec) -> frozenset[str]:
    return frozenset(
        ref.field
        for node in graph.nodes
        for ref in node.config.input_bindings.values()
        if ref.source is BindingSource.EXTERNAL and ref.field is not None
    )


def validate_external_bindings(
    graph: GraphSpec,
    *,
    allowed_fields: Collection[str],
) -> None:
    bound = external_binding_fields(graph)
    if not bound:
        return
    allowed = set(allowed_fields)
    unknown = sorted(bound - allowed)
    if unknown:
        unknown_list = ", ".join(repr(field) for field in unknown)
        raise GraphValidationError(
            f"external binding field(s) {unknown_list} not in allowed "
            "external fields"
        )


def validate_binding_ref(
    ref: BindingRef,
    nodes_by_id: dict[str, NodeSpec],
) -> None:
    if ref.source is BindingSource.EXTERNAL:
        return
    if ref.node_id not in nodes_by_id:
        raise GraphValidationError(
            f"ref {ref.ref!r} points at unknown node {ref.node_id!r}"
        )
    if ref.field is None:
        return
    source_node = nodes_by_id[ref.node_id]
    output_names = {field.name for field in source_node.config.output_fields()}
    if ref.field not in output_names:
        raise GraphValidationError(
            f"ref {ref.ref!r} points at unknown field {ref.field!r} "
            f"on node {ref.node_id!r}"
        )


def validate_acyclic_graph(nodes: tuple[NodeSpec, ...]) -> None:
    topological_order(nodes)


def topological_order(nodes: tuple[NodeSpec, ...]) -> tuple[NodeSpec, ...]:
    node_ids = {node.id for node in nodes}
    by_id = {node.id: node for node in nodes}
    done: set[str] = set()
    remaining = set(node_ids)
    ordered: list[NodeSpec] = []
    while remaining:
        ready = sorted(
            node_id
            for node_id in remaining
            if by_id[node_id].dependencies() <= done
        )
        if not ready:
            stuck = ", ".join(sorted(remaining))
            raise GraphValidationError(f"graph has a cycle among: {stuck}")
        ordered.extend(by_id[node_id] for node_id in ready)
        done.update(ready)
        remaining.difference_update(ready)
    return tuple(ordered)


def _exception_failure_class(error: BaseException) -> str | None:
    failure_class = getattr(error, "failure_class", None)
    if isinstance(failure_class, StrEnum):
        return failure_class.value
    if isinstance(failure_class, str):
        return failure_class
    failure_class = getattr(type(error), "failure_class", None)
    if isinstance(failure_class, StrEnum):
        return failure_class.value
    if isinstance(failure_class, str):
        return failure_class
    return None


def _exception_error_type(error: BaseException) -> str:
    error_type = getattr(error, "error_type", None)
    if isinstance(error_type, str):
        return error_type
    return f"{type(error).__module__}.{type(error).__qualname__}"


def _exception_type_name(error: BaseException) -> str:
    return f"{type(error).__module__}.{type(error).__qualname__}"


def _root_exception(error: BaseException) -> BaseException:
    current = error
    while True:
        underlying = getattr(current, "underlying", None)
        if not isinstance(underlying, BaseException):
            return current
        current = underlying


def _exception_metadata(error: BaseException) -> dict[str, Any]:
    metadata = getattr(error, "metadata", None)
    result = dict(metadata) if isinstance(metadata, dict) else {}
    if getattr(error, "underlying", None) is not None:
        result.setdefault(
            "underlying_exception_type",
            _exception_type_name(_root_exception(error)),
        )
    return result
