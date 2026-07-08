# GraphSpec is valid by construction

A `GraphSpec` runs full structural validation (non-empty, unique node ids,
terminal node present, legal binding refs, single external namespace, no
namespace/node-id collision, acyclic) in a Pydantic `model_validator`, so any
`GraphSpec` instance that exists is structurally valid — there is no separate
`validate()` step in the API, and invalid specs are unrepresentable. We chose
this because dr-graph specs are optimizer genomes and digest/persistence
inputs: downstream code (hashing, execution, storage) should never have to ask
"did anyone validate this?", and invalid mutations should die loudly at
construction. The accepted cost is that tooling which needs to hold a broken
spec in memory (repair, migration, partial editors) must work with raw dicts
until the spec is fixed.
