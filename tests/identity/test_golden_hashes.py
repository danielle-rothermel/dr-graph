from __future__ import annotations

import json
from pathlib import Path

import pytest
from dr_serialize import canonical_identity_json

from dr_graph import graph_config_identity_document, graph_hash
from tests.identity.golden_graphs import GOLDEN_GRAPHS

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "graph_hashes_golden.json"


def load_fixture() -> dict[str, dict[str, str]]:
    return json.loads(FIXTURE_PATH.read_text())


@pytest.mark.parametrize("name", sorted(GOLDEN_GRAPHS))
def test_golden_graph_hash_reproduces(name: str) -> None:
    entry = load_fixture()[name]
    config = GOLDEN_GRAPHS[name]

    document = graph_config_identity_document(config)
    assert (
        canonical_identity_json(document) == entry["canonical_identity_json"]
    )
    assert graph_hash(config) == entry["graph_hash"]


def test_golden_fixture_covers_every_graph() -> None:
    assert set(load_fixture()) == set(GOLDEN_GRAPHS)


def test_schema_version_change_changes_graph_hash() -> None:
    from dr_serialize import build_identity_document, identity_document_hash

    from dr_graph.identity import (
        GRAPH_CONFIG_IDENTITY_SCHEMA,
        GRAPH_CONFIG_IDENTITY_SCHEMA_VERSION,
        graph_config_identity_payload,
    )

    config = GOLDEN_GRAPHS["encdec_graph"]
    payload = graph_config_identity_payload(config)
    v1 = identity_document_hash(
        build_identity_document(
            schema=GRAPH_CONFIG_IDENTITY_SCHEMA,
            schema_version=GRAPH_CONFIG_IDENTITY_SCHEMA_VERSION,
            payload=payload,
        )
    )
    v2 = identity_document_hash(
        build_identity_document(
            schema=GRAPH_CONFIG_IDENTITY_SCHEMA,
            schema_version=GRAPH_CONFIG_IDENTITY_SCHEMA_VERSION + 1,
            payload=payload,
        )
    )
    assert v1 == graph_hash(config)
    assert v1 != v2
