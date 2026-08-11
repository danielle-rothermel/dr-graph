# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2026-08-11

### Removed

- `GraphRunResult.attempt_evidence_refs` and `GraphRunResult.provenance`
  (callers stamp association externally; per-leg evidence stays in
  `NodeOutput.metadata`).

### Changed

- Ratified graph-config ownership, serial intra-graph execution, and
  `graph_hash` as a composable inner identity layer in terms and contracts.
- `NodeError` now captures exception tracebacks and records metadata extraction
  losses in `metadata["dropped_metadata"]` instead of dropping them silently.
- `NodeError.error_type` is always the real exception type; caller-declared
  labels move to `metadata["declared_error_type"]`.
- dr-graph infrastructure errors (`InputResolutionError`, `NodeExecutionError`)
  carry `failure_class="infrastructure"`.
- `NodeOutcome` gains `outcome_source` (`fresh` / `reused`) to distinguish
  nodes invoked in the current run from completed outputs reused at start.
- Cancellation (`asyncio.CancelledError`, `KeyboardInterrupt`) records partial
  graph-run evidence on `GraphRunInterruptedError.partial_result` before
  re-raising.
- `NodeOutcomeStatus.CANCELLED` and `GraphRunStatus.CANCELLED` represent an
  interrupted in-flight node.

## [0.1.2] - 2026-08-06

### Added

- `dr_graph.flow` provides exact deterministic single-source, single-sink min-cost flow over nonnegative integer capacities and costs.
- `dr_graph.flow.transport` provides exact separable convex transportation from nonnegative, nondecreasing integer marginal costs.

### Notes

- The top-level `dr_graph` computation API remains separate from the flow optimization namespace.
- The README and authoritative terms and contracts describe both optimization namespaces and their stable public shapes.
- Tag-triggered releases verify that the release commit belongs to `main` before publishing.

## [0.1.1] - 2026-08-05

### Changed

- Reorganized source and tests into functional subpackages while preserving the root `dr_graph` facade; retired flat internal import paths are no longer provided.
- Strengthened definition, execution, continuation, and result validation with a closed definition schema version, named-output checks, dependency-closed completed outputs, complete callback outputs, pre-execution strict JSON inputs, and coherent graph-run outcomes.
- Made callback failure normalization cycle-safe and non-throwing for faulty diagnostic accessors while preserving each valid metadata entry independently.
- Updated the serialization contract dependency to `dr-serialize>=0.1.2,<0.2.0`.
- Replaced the README with a functional package map and current public contract sketches.
- Audited repository documentation and retained only succinct, non-obvious docstrings and comments.
- Added authoritative terminology and standing-contract TOML references with a GitHub Pages viewer.
- Added repository definitions validation, a tracked local commit gate, hardened Depot CI, and verified tag-triggered PyPI publication.

### Removed

- Removed the unreachable `GraphRunStatus.PARTIAL` state.

## [0.1.0] - 2026-07-24

First public release.

### Added

- Graph Config identity contract: `graph_hash` is the versioned identity, backed by schema `dr_graph.graph_config` v1 and gated by golden fixtures.
- `GraphConfig` / `NodeConfig` model, including Node Input Sources and Variables.
- `GraphDefinition` / `NodeDefinition` materialization artifact.
- Sequential `execute_graph` interpreter with caller-supplied node behavior.
- Neutral builders and `inline_subgraph` composition.

### Notes

- Any identity-affecting change requires a schema-version bump and regeneration of the golden fixtures.
