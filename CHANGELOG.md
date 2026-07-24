# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - TBD

First public release.

### Added

- Graph Config identity contract: `graph_hash` is the versioned identity, backed by schema `dr_graph.graph_config` v1 and gated by golden fixtures.
- `GraphConfig` / `NodeConfig` model, including Node Input Sources and Variables.
- `GraphDefinition` / `NodeDefinition` materialization artifact.
- Pure sequential `execute_graph` interpreter.
- Neutral builders and `inline_subgraph` composition.

### Notes

- Any identity-affecting change requires a schema-version bump and regeneration of the golden fixtures.
