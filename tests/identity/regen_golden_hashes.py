"""Regenerate tests/identity/fixtures/graph_hashes_golden.json.

Run only after an intentional Graph Config identity change (a coordinated
break) — never to paper over a mismatch. Usage:

    uv run python -m tests.identity.regen_golden_hashes
"""

from __future__ import annotations

import json
from pathlib import Path

from dr_serialize import canonical_identity_json

from dr_graph import graph_config_identity_document, graph_hash
from tests.identity.golden_graphs import GOLDEN_GRAPHS

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "graph_hashes_golden.json"


def build_fixture() -> dict[str, dict[str, str]]:
    return {
        name: {
            "canonical_identity_json": canonical_identity_json(
                graph_config_identity_document(config)
            ),
            "graph_hash": graph_hash(config),
        }
        for name, config in GOLDEN_GRAPHS.items()
    }


def main() -> None:
    fixture = build_fixture()
    FIXTURE_PATH.write_text(json.dumps(fixture, indent=2) + "\n")


if __name__ == "__main__":
    main()
