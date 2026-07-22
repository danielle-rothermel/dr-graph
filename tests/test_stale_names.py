"""No migration-source spelling survives the coordinated break.

Scans shipped source, exports, and tests for retired names. The scan test
itself is exempt (it must name the retired spellings to forbid them).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = (REPO_ROOT / "src", REPO_ROOT / "tests")

# Retired migration-source spellings that must not remain anywhere in
# shipped source, exports, serialized schemas, or tests.
STALE_NAMES = (
    "GraphSpec",
    "NodeSpec",
    "FieldSpec",
    "BindingRef",
    "BindingSource",
    "graph_digest",
    "GRAPH_DIGEST_LENGTH",
    "canonical_graph_payload",
    "input_bindings",
    "as_binding_ref",
    "validate_external_bindings",
    "external_binding_fields",
    "validate_binding_ref",
    "validate_graph_spec",
    "graph_digests_golden",
)

# This file is the only allowed place the retired spellings may appear.
EXEMPT_FILES = frozenset({Path(__file__).resolve()})


def _scanned_files() -> list[Path]:
    files: list[Path] = []
    for scan_dir in SCAN_DIRS:
        for path in scan_dir.rglob("*.py"):
            if path.resolve() in EXEMPT_FILES:
                continue
            files.append(path)
    return files


def _scanned_json() -> list[Path]:
    return list((REPO_ROOT / "tests" / "fixtures").rglob("*.json"))


@pytest.mark.parametrize("stale", STALE_NAMES)
def test_no_stale_migration_source_names(stale: str) -> None:
    pattern = re.compile(rf"\b{re.escape(stale)}\b")
    offenders: list[str] = []
    for path in [*_scanned_files(), *_scanned_json()]:
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                rel = path.relative_to(REPO_ROOT)
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, (
        f"stale name {stale!r} still present:\n" + "\n".join(offenders)
    )
