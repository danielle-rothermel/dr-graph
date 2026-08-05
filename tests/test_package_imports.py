"""Import hygiene: the interpreter must stay dependency-light."""

from __future__ import annotations

import subprocess
import sys
import textwrap


def test_functional_package_facades_are_importable() -> None:
    from dr_graph.assembly import graph
    from dr_graph.configuration import GraphConfig
    from dr_graph.definitions import GraphDefinition
    from dr_graph.execution import execute_graph
    from dr_graph.identity import graph_hash
    from dr_graph.results import GraphRunResult

    assert all(
        symbol is not None
        for symbol in (
            graph,
            GraphConfig,
            GraphDefinition,
            execute_graph,
            graph_hash,
            GraphRunResult,
        )
    )


def test_import_loads_no_heavy_dependencies() -> None:
    script = textwrap.dedent(
        """
        import sys

        import dr_graph

        blocked = (
            "httpx",
            "openai",
            "dspy",
            "dbos",
            "psycopg",
            "sqlalchemy",
        )
        loaded = [module for module in blocked if module in sys.modules]
        if loaded:
            raise SystemExit(",".join(loaded))
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
