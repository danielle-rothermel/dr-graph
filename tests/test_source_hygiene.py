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
SOURCE_PACKAGE = REPO_ROOT / "src" / "dr_graph"
FUNCTIONAL_PACKAGES = frozenset(
    {
        "assembly",
        "configuration",
        "core",
        "definitions",
        "execution",
        "identity",
        "results",
    }
)

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
# `.defs/api-notes.md` is also exempt: it legitimately discusses the retired
# names as rename history, so scanning it would trip the test on purpose.
EXEMPT_FILES = frozenset(
    {
        Path(__file__).resolve(),
        (REPO_ROOT / ".defs" / "api-notes.md").resolve(),
    }
)


def _scanned_files() -> list[Path]:
    files: list[Path] = []
    for scan_dir in SCAN_DIRS:
        for path in scan_dir.rglob("*.py"):
            if path.resolve() in EXEMPT_FILES:
                continue
            files.append(path)
    return files


def _scanned_json() -> list[Path]:
    return list((REPO_ROOT / "tests").rglob("*.json"))


def _scanned_docs() -> list[Path]:
    # Current-facing prose docs must also stay free of retired spellings:
    # README.md, everything under docs/ (docs/adr/ is removed, so no ADR
    # exclusion is needed), and the .defs/vocab.html glossary. api-notes.md is
    # excluded via EXEMPT_FILES because it records rename history on purpose.
    docs: list[Path] = [
        REPO_ROOT / "README.md",
        REPO_ROOT / ".defs" / "vocab.html",
    ]
    for pattern in ("*.md", "*.html"):
        docs.extend((REPO_ROOT / "docs").rglob(pattern))
    return [
        path
        for path in docs
        if path.exists() and path.resolve() not in EXEMPT_FILES
    ]


@pytest.mark.parametrize("stale", STALE_NAMES)
def test_no_stale_migration_source_names(stale: str) -> None:
    pattern = re.compile(rf"\b{re.escape(stale)}\b")
    offenders: list[str] = []
    for path in [*_scanned_files(), *_scanned_json(), *_scanned_docs()]:
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                rel = path.relative_to(REPO_ROOT)
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, f"stale name {stale!r} still present:\n" + "\n".join(
        offenders
    )


def test_source_and_test_trees_share_functional_packages() -> None:
    source_packages = {
        path.name
        for path in SOURCE_PACKAGE.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    test_packages = {
        path.name
        for path in (REPO_ROOT / "tests").iterdir()
        if path.is_dir() and (path / "__init__.py").exists()
    }

    assert source_packages == FUNCTIONAL_PACKAGES
    assert test_packages == FUNCTIONAL_PACKAGES
    assert {
        path.name for path in SOURCE_PACKAGE.iterdir() if path.is_file()
    } == {"__init__.py", "py.typed"}
