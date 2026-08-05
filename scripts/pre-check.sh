#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

staged_paths_file=$(mktemp "${TMPDIR:-/tmp}/dr-graph-staged-paths.XXXXXX")
trap 'rm -f -- "$staged_paths_file"' EXIT
git diff --cached --name-only --diff-filter=ACMR -z -- >"$staged_paths_file"

staged_python_paths=()
while IFS= read -r -d '' path; do
  case "$path" in
    src/*.py | tests/*.py) staged_python_paths+=("$path") ;;
  esac
done <"$staged_paths_file"

partially_staged_paths=()
if ((${#staged_python_paths[@]} > 0)); then
  for path in "${staged_python_paths[@]}"; do
    if git diff --quiet -- "$path"; then
      continue
    else
      status=$?
    fi

    if ((status == 1)); then
      partially_staged_paths+=("$path")
    else
      printf 'pre-check: failed to inspect %q\n' "$path" >&2
      exit "$status"
    fi
  done
fi

if ((${#partially_staged_paths[@]} > 0)); then
  printf 'pre-check: refusing to modify partially staged Python files:\n' >&2
  printf '  %q\n' "${partially_staged_paths[@]}" >&2
  printf 'Stage or unstage each file completely, then retry.\n' >&2
  exit 1
fi

if ((${#staged_python_paths[@]} > 0)); then
  printf 'pre-check: fixing and formatting %d staged Python file(s)\n' \
    "${#staged_python_paths[@]}"
  uv run --locked ruff check --fix -- "${staged_python_paths[@]}"
  uv run --locked ruff format -- "${staged_python_paths[@]}"
  git add -- "${staged_python_paths[@]}"
fi

printf 'pre-check: running full-repository checks\n'
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked ty check
uv run --locked pytest -q
uvx tombi@1.2.5 lint .defs/terms.toml .defs/contracts.toml
uv run --locked python scripts/check_defs.py
