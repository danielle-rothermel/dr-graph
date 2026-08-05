from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dr_serialize import build_identity_document, identity_document_hash

if TYPE_CHECKING:
    from dr_serialize import IdentityDocument

    from dr_graph.configuration.graphs import GraphConfig

# Changing either constant changes every graph hash; goldens pin both.
GRAPH_CONFIG_IDENTITY_SCHEMA = "dr_graph.graph_config"
GRAPH_CONFIG_IDENTITY_SCHEMA_VERSION = 1


def graph_config_identity_payload(graph: GraphConfig) -> dict[str, Any]:
    """Build the static, identity-bearing Graph Config payload.

    Only known structural tuples are converted to lists. Other leaves remain
    raw so strict JSON validation rejects unsupported or non-finite variable
    values instead of coercing them into colliding identities.
    """
    payload = graph.model_dump(mode="python")
    payload["nodes"] = [
        {**node, "fields": list(node["fields"])} for node in payload["nodes"]
    ]
    return payload


def graph_config_identity_document(graph: GraphConfig) -> IdentityDocument:
    return build_identity_document(
        schema=GRAPH_CONFIG_IDENTITY_SCHEMA,
        schema_version=GRAPH_CONFIG_IDENTITY_SCHEMA_VERSION,
        payload=graph_config_identity_payload(graph),
    )


def graph_hash(graph: GraphConfig) -> str:
    """Return the untruncated SHA-256 hash of the graph identity document."""
    return identity_document_hash(graph_config_identity_document(graph))
