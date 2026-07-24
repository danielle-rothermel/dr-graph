from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dr_serialize import build_identity_document, identity_document_hash

if TYPE_CHECKING:
    from dr_serialize import IdentityDocument

    from dr_graph.spec import GraphConfig

# dr-graph owns this Graph Config identity schema name and version. Bumping
# the version changes every graph_hash; goldens pin both.
GRAPH_CONFIG_IDENTITY_SCHEMA = "dr_graph.graph_config"
GRAPH_CONFIG_IDENTITY_SCHEMA_VERSION = 1


def _tuples_to_lists(value: Any) -> Any:
    """Normalize tuples to lists, recursively, leaving all leaves raw.

    ``model_dump(mode="python")`` preserves raw leaf values (crucially,
    non-finite floats stay ``NaN``/``Inf`` rather than being silently coerced
    to JSON ``null`` as ``mode="json")`` does), but emits ``tuple`` for the
    ``tuple[...]``-typed fields. dr-serialize's ``validate_strict_json``
    accepts ``list`` but rejects ``tuple`` as an unsupported type, so the
    identity payload converts container tuples to lists here. Leaves are left
    untouched so every unsupported or non-finite Variable value reaches
    dr-serialize's recursive validator and is rejected before canonicalization.
    """
    if isinstance(value, (list, tuple)):
        return [_tuples_to_lists(item) for item in value]
    if isinstance(value, dict):
        return {key: _tuples_to_lists(item) for key, item in value.items()}
    return value


def graph_config_identity_payload(graph: GraphConfig) -> dict[str, Any]:
    """The Graph Config Identity Payload: every static identity-bearing field.

    dr-graph deliberately selects exactly the static Graph Config fields —
    the ordered concrete Node configs (each carrying its node_id, Node
    Definition reference/``node_type``, declared fields, Node Input Sources,
    declared output, and static Variable assignments) and the single terminal
    Node id. No runtime or storage fields are included.

    Dumped in ``mode="python"`` (not ``mode="json"``) so that raw, uncoerced
    leaf values — including non-finite floats in a Node's ``variables`` —
    reach dr-serialize's ``validate_strict_json`` and are rejected there,
    rather than being silently coerced (e.g. ``NaN``/``Inf`` to ``null``)
    into a colliding identity. Container tuples are normalized to lists for
    the validator; ``NodeInputSourceRef`` still serializes to its string form.
    """
    return _tuples_to_lists(graph.model_dump(mode="python"))


def graph_config_identity_document(graph: GraphConfig) -> IdentityDocument:
    return build_identity_document(
        schema=GRAPH_CONFIG_IDENTITY_SCHEMA,
        schema_version=GRAPH_CONFIG_IDENTITY_SCHEMA_VERSION,
        payload=graph_config_identity_payload(graph),
    )


def graph_hash(graph: GraphConfig) -> str:
    """Full 64-char lowercase SHA-256 Graph Hash via dr-serialize.

    Computed as the Identity Hash of the Graph Config Identity Document.
    No truncation and no length parameter; distinct from any Content Hash.
    """
    return identity_document_hash(graph_config_identity_document(graph))
