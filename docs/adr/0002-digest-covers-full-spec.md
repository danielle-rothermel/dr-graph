# The graph hash covers every identity-bearing Graph Config field

> Updated for the coordinated identity break: the truncated, unversioned
> `graph_digest` over a raw `{"graph": ...}` payload is replaced by
> `graph_hash` — the full 64-char lowercase SHA-256 Identity Hash of the
> Graph Config Identity Document `{schema, schema_version, payload}` computed
> through dr-serialize's identity API. The coverage principle below is
> unchanged; only the mechanism (versioned Identity Document, full hash) and
> the names changed.

`graph_hash` hashes the Canonical Identity JSON of the entire Graph Config
Identity Payload, including every open Variable assignment on Node configs —
there is no hash-excluded "annotation space" inside a config. We chose this
because the hash is the identity of a treatment: values consumers store in
open config fields (prompt templates, provider selections) are
treatment-defining, and any exclusion rule would let byte-different configs
silently share an identity. The flip side of the contract: anything
identity-irrelevant (provenance, generation lineage, timestamps, notes) must
live outside the Identity Payload, keyed by the `graph_hash` — never in
identity-bearing config fields. dr-graph selects the payload fields; it does
not reimplement canonicalization or hashing.
