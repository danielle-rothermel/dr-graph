# Subgraph composition flattens; there is no nesting in the data model

`inline_subgraph` composes by returning the subgraph's nodes renamed under a
prefix with refs rewired; the parent assembles an ordinary flat `GraphSpec`.
Composition happens on the code side of the data/code line and evaporates at
build time — however a spec was assembled, the same computation converges to
the same bytes and one digest. We rejected hierarchical nesting because it
creates a two-representation identity problem (a flat graph and a nested
graph with identical computation would hash differently, forking treatment
identities) and forces hierarchy into every layer: port declarations for
cross-boundary validation, a recursive interpreter, path-keyed outcomes and
resume state, and a scoped ref grammar.

Accepted consequences: the prefix is identity-affecting (renaming a prefix
forks the digest — acceptable because spec builders choose prefixes
deterministically), and subgraph boundaries do not survive into the spec or
run results. Callers that need boundary or provenance information store it
outside the spec, keyed by digest (see ADR 0002).
