# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-08-06

### Added

- `dr_graph.flow` provides exact deterministic min-cost flow over integer capacities and costs.
- `dr_graph.flow.transport` provides exact separable convex transportation from nondecreasing marginal costs.

### Notes

- The top-level `dr_graph` computation API remains separate from the flow optimization namespace.

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
