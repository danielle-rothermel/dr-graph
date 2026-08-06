"""Import hygiene for the public package boundaries."""

from __future__ import annotations

import subprocess
import sys
import textwrap


def test_import_loads_no_known_forbidden_application_dependencies() -> None:
    script = textwrap.dedent(
        """
        import sys

        import dr_graph

        if "dr_graph.flow" in sys.modules:
            raise SystemExit("dr_graph.flow loaded eagerly")

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


def test_flow_api_exports_only_from_its_public_namespace() -> None:
    import dr_graph
    import dr_graph.flow

    assert "FlowProblem" in dr_graph.flow.__all__
    assert "solve_min_cost_flow" in dr_graph.flow.__all__
    assert set(dr_graph.flow.__all__).isdisjoint(dr_graph.__all__)
