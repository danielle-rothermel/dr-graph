# The graph digest covers every byte of the spec

`graph_digest` hashes the canonical JSON dump of the entire `GraphSpec`,
including every open dict on node configs — there is no digest-excluded
"annotation space" inside a spec. We chose this because the digest is the
identity of a treatment: values consumers store in open spec fields (prompt
templates, provider selections) are treatment-defining, and any exclusion rule
would let byte-different specs silently share an identity. The flip side of
the contract: anything identity-irrelevant (provenance, generation lineage,
timestamps, notes) must live outside the spec, keyed by the digest — never in
spec fields.
