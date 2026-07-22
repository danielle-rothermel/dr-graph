# Subgraph composition flattens; there is no nesting in the data model

> Updated for the coordinated identity break: `GraphSpec` is now
> `GraphConfig` and `graph_digest` is now the full versioned `graph_hash`.
> The flattening decision below is unchanged.

`inline_subgraph` composes by returning the subgraph's nodes renamed under a
prefix with Node Input Sources rewired; the parent assembles an ordinary flat
`GraphConfig`. Composition happens on the code side of the data/code line and
evaporates at build time — however a config was assembled, the same
computation converges to the same identity payload and one `graph_hash`. We
rejected hierarchical nesting because it creates a two-representation identity
problem (a flat graph and a nested graph with identical computation would hash
differently, forking treatment identities) and forces hierarchy into every
layer: port declarations for cross-boundary validation, a recursive
interpreter, path-keyed outcomes and resume state, and a scoped ref grammar.

Accepted consequences: the prefix is identity-affecting (renaming a prefix
forks the `graph_hash` — acceptable because config builders choose prefixes
deterministically), and subgraph boundaries do not survive into the config or
run results. Callers that need boundary or provenance information store it
outside the config, keyed by `graph_hash` (see ADR 0002).
