#!/usr/bin/env python3
from __future__ import annotations

import sys
import tomllib
from collections import Counter
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING

import dr_graph
import dr_graph.flow
import dr_graph.flow.transport

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

TERM_REQUIRED_KEYS = frozenset({"name", "definition"})
TERM_ALLOWED_KEYS = TERM_REQUIRED_KEYS | {
    "categories",
    "exported_symbols",
    "is_a",
    "part_of",
}
TERM_LIST_KEYS = ("categories", "exported_symbols", "is_a", "part_of")
RELATIONSHIP_KEYS = ("is_a", "part_of")

CONTRACT_REQUIRED_KEYS = frozenset({"date", "rationale", "statement", "title"})
CONTRACT_ALLOWED_KEYS = CONTRACT_REQUIRED_KEYS | {"check"}

REQUIRED_ASSETS = frozenset(
    {
        "contracts.toml",
        "defs-render.js",
        "doc.css",
        "favicon.svg",
        "index.html",
        "smol-toml.js",
        "terms.schema.json",
        "terms.toml",
    }
)
REQUIRED_INDEX_SLOTS = frozenset(
    {
        ("terms.toml", "terms"),
        ("contracts.toml", "contracts"),
    }
)


def _require(condition: bool, message: str) -> None:  # noqa: FBT001
    if not condition:
        raise AssertionError(message)


def _nonempty_string(value: object, location: str) -> str:
    _require(
        isinstance(value, str) and bool(value.strip()),
        f"{location} must be a nonempty string",
    )
    return value


def _string_list(value: object, location: str) -> list[str]:
    _require(
        isinstance(value, list) and value,
        f"{location} must be a nonempty list",
    )
    strings = [
        _nonempty_string(item, f"{location}[{index}]")
        for index, item in enumerate(value)
    ]
    duplicates = sorted(
        item for item, count in Counter(strings).items() if count > 1
    )
    _require(
        not duplicates, f"{location} contains duplicate values: {duplicates}"
    )
    return strings


def _tables(
    document: object,
    *,
    key: str,
    source: str,
) -> list[dict[str, object]]:
    _require(isinstance(document, dict), f"{source} must contain a TOML table")
    _require(
        set(document) == {key},
        f"{source} must contain only the top-level key {key!r}",
    )
    entries = document[key]
    _require(
        isinstance(entries, list) and entries,
        f"{source}.{key} must be a nonempty array of tables",
    )
    for index, entry in enumerate(entries):
        _require(
            isinstance(entry, dict),
            f"{source}.{key}[{index}] must be a table",
        )
    return entries


def _validate_keys(
    table: Mapping[str, object],
    *,
    required: frozenset[str],
    allowed: frozenset[str],
    location: str,
) -> None:
    keys = set(table)
    missing = sorted(required - keys)
    unknown = sorted(keys - allowed)
    _require(not missing, f"{location} is missing required keys: {missing}")
    _require(not unknown, f"{location} has unknown keys: {unknown}")


def validate_terms(document: object) -> list[dict[str, object]]:
    terms = _tables(document, key="terms", source="terms.toml")
    names: list[str] = []

    for index, term in enumerate(terms):
        location = f"terms.toml.terms[{index}]"
        _validate_keys(
            term,
            required=TERM_REQUIRED_KEYS,
            allowed=TERM_ALLOWED_KEYS,
            location=location,
        )
        name = _nonempty_string(term["name"], f"{location}.name")
        _nonempty_string(term["definition"], f"{location}.definition")
        names.append(name)
        for key in TERM_LIST_KEYS:
            if key in term:
                _string_list(term[key], f"{location}.{key}")

    duplicate_names = sorted(
        name for name, count in Counter(names).items() if count > 1
    )
    _require(
        not duplicate_names,
        f"terms.toml has duplicate term names: {duplicate_names}",
    )
    _validate_relationships(terms, names)
    _validate_exports(terms)
    return terms


def _validate_relationships(
    terms: Iterable[Mapping[str, object]], names: Iterable[str]
) -> None:
    known_names = set(names)
    graph: dict[str, list[str]] = {name: [] for name in known_names}

    for term in terms:
        name = str(term["name"])
        linked_targets: set[str] = set()
        for key in RELATIONSHIP_KEYS:
            targets = term.get(key, [])
            for target in targets:
                _require(
                    target in known_names,
                    f"term {name!r} {key} target {target!r} does not exist",
                )
                _require(
                    target != name,
                    f"term {name!r} cannot link to itself via {key}",
                )
                _require(
                    target not in linked_targets,
                    f"term {name!r} links to {target!r} more than once",
                )
                linked_targets.add(target)
                graph[name].append(target)

    _require_acyclic(graph)


def _require_acyclic(graph: Mapping[str, list[str]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()
    path: list[str] = []

    def visit(name: str) -> None:
        if name in visiting:
            cycle_start = path.index(name)
            cycle = " -> ".join([*path[cycle_start:], name])
            raise AssertionError(
                f"terms.toml relationship cycle detected: {cycle}"
            )
        if name in visited:
            return
        visiting.add(name)
        path.append(name)
        for target in graph[name]:
            visit(target)
        path.pop()
        visiting.remove(name)
        visited.add(name)

    for name in sorted(graph):
        visit(name)


def _validate_exports(terms: Iterable[Mapping[str, object]]) -> None:
    namespaces = {
        "dr_graph": dr_graph,
        "dr_graph.flow": dr_graph.flow,
        "dr_graph.flow.transport": dr_graph.flow.transport,
    }
    public_symbols: set[str] = set()
    qualified_exports: set[str] = set()
    root_exports: set[str] = set()
    subpackage_exports: set[str] = set()
    missing_attributes: list[str] = []

    for namespace, module in namespaces.items():
        module_all = getattr(module, "__all__", None)
        _require(
            isinstance(module_all, (list, tuple)) and bool(module_all),
            f"{namespace}.__all__ must be a nonempty list or tuple",
        )
        exports = [
            _nonempty_string(
                symbol,
                f"{namespace}.__all__[{index}]",
            )
            for index, symbol in enumerate(module_all)
        ]
        duplicates = sorted(
            symbol for symbol, count in Counter(exports).items() if count > 1
        )
        _require(
            not duplicates,
            f"{namespace}.__all__ has duplicates: {duplicates}",
        )
        for symbol in exports:
            qualified_symbol = f"{namespace}.{symbol}"
            public_symbols.add(qualified_symbol)
            if namespace == "dr_graph":
                root_exports.add(symbol)
            else:
                qualified_exports.add(qualified_symbol)
                subpackage_exports.add(symbol)
            if not hasattr(module, symbol):
                missing_attributes.append(qualified_symbol)

    mapped_exports = [
        symbol for term in terms for symbol in term.get("exported_symbols", [])
    ]
    mapped_counts = Counter(mapped_exports)
    duplicate_mappings = sorted(
        symbol for symbol, count in mapped_counts.items() if count > 1
    )
    qualified_mappings = {symbol for symbol in mapped_exports if "." in symbol}
    short_mappings = set(mapped_exports) - qualified_mappings
    missing_mappings = sorted(
        (root_exports - short_mappings)
        | (qualified_exports - qualified_mappings)
    )
    unknown_mappings = sorted(
        (short_mappings - root_exports) | (qualified_mappings - public_symbols)
    )
    root_subpackage_overlap = sorted(root_exports & subpackage_exports)

    _require(
        not duplicate_mappings,
        f"exported symbols mapped more than once: {duplicate_mappings}",
    )
    _require(
        not missing_mappings,
        "public __all__ symbols missing from terms.toml: "
        f"{missing_mappings}",
    )
    _require(
        not unknown_mappings,
        "terms.toml maps symbols absent from public __all__ declarations: "
        f"{unknown_mappings}",
    )
    _require(
        not root_subpackage_overlap,
        "dr_graph and its functional subpackages export the same symbols: "
        f"{root_subpackage_overlap}",
    )
    _require(
        not missing_attributes,
        "public __all__ symbols missing from their packages: "
        f"{missing_attributes}",
    )


def validate_contracts(document: object) -> list[dict[str, object]]:
    contracts = _tables(
        document,
        key="contracts",
        source="contracts.toml",
    )
    for index, contract in enumerate(contracts):
        location = f"contracts.toml.contracts[{index}]"
        _validate_keys(
            contract,
            required=CONTRACT_REQUIRED_KEYS,
            allowed=CONTRACT_ALLOWED_KEYS,
            location=location,
        )
        for key in ("title", "statement", "rationale"):
            _nonempty_string(contract[key], f"{location}.{key}")
        contract_date = _nonempty_string(contract["date"], f"{location}.date")
        try:
            parsed_date = date.fromisoformat(contract_date)
        except ValueError as error:
            raise AssertionError(
                f"{location}.date must use YYYY-MM-DD format"
            ) from error
        _require(
            parsed_date.isoformat() == contract_date,
            f"{location}.date must use YYYY-MM-DD format",
        )
        if "check" in contract:
            _nonempty_string(contract["check"], f"{location}.check")
    return contracts


class _IndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.slots: set[tuple[str, str]] = set()
        self.asset_refs: set[str] = set()

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if tag == "tbody":
            defs_file = attributes.get("data-defs-file")
            defs_kind = attributes.get("data-defs-kind")
            if defs_file is not None and defs_kind is not None:
                self.slots.add((defs_file, defs_kind))
        for key in ("href", "src"):
            reference = attributes.get(key)
            if reference is not None:
                self.asset_refs.add(reference)


def validate_defs_surface(defs_dir: Path) -> None:
    for asset in sorted(REQUIRED_ASSETS):
        path = defs_dir / asset
        _require(path.is_file(), f"required .defs asset is missing: {asset}")
        _require(
            path.stat().st_size > 0, f"required .defs asset is empty: {asset}"
        )
    parser = _IndexParser()
    parser.feed((defs_dir / "index.html").read_text(encoding="utf-8"))
    missing_slots = sorted(REQUIRED_INDEX_SLOTS - parser.slots)
    _require(
        not missing_slots,
        f"index.html is missing .defs slots: {missing_slots}",
    )
    required_refs = {"defs-render.js", "doc.css", "favicon.svg"}
    missing_refs = sorted(required_refs - parser.asset_refs)
    _require(
        not missing_refs,
        f"index.html is missing required asset references: {missing_refs}",
    )


def _load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as file:
        return tomllib.load(file)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    defs_dir = repo_root / ".defs"
    try:
        terms = validate_terms(_load_toml(defs_dir / "terms.toml"))
        contracts = validate_contracts(_load_toml(defs_dir / "contracts.toml"))
        validate_defs_surface(defs_dir)
    except (AssertionError, OSError, tomllib.TOMLDecodeError) as error:
        print(f"check_defs: ERROR: {error}", file=sys.stderr)
        return 1

    print(
        "check_defs: OK: "
        f"{len(terms)} terms, {len(contracts)} contracts, "
        f"{len(dr_graph.__all__)} exports"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
