from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dr_serialize import build_identity_document, identity_hash

if TYPE_CHECKING:
    from dr_serialize import IdentityDocument

    from dr_graph.spec import GraphConfig

# dr-graph owns this Graph Config identity schema name and version. Bumping
# the version changes every graph_hash; goldens pin both.
GRAPH_CONFIG_IDENTITY_SCHEMA = "dr_graph.graph_config"
GRAPH_CONFIG_IDENTITY_SCHEMA_VERSION = 1


def graph_config_identity_payload(graph: GraphConfig) -> dict[str, Any]:
    """The Graph Config Identity Payload: every static identity-bearing field.

    dr-graph deliberately selects exactly the static Graph Config fields —
    the ordered concrete Node configs (each carrying its node_id, Node
    Definition reference/``node_type``, declared fields, Node Input Sources,
    declared output, and static Variable assignments) and the single terminal
    Node id. No runtime or storage fields are included.
    """
    return graph.model_dump(mode="json")


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
    return identity_hash(graph_config_identity_document(graph))
