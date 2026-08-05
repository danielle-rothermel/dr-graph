"""Import hygiene: the interpreter must stay dependency-light."""

from __future__ import annotations

import subprocess
import sys
import textwrap


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
