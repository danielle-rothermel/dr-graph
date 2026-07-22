# GraphConfig is valid by construction

> Updated for the coordinated identity break: `GraphSpec` is now
> `GraphConfig` and the native Node representation is the single `NodeConfig`
> lifecycle role. The valid-by-construction decision below is unchanged.

A `GraphConfig` runs full structural validation (non-empty, unique node ids,
terminal node present, legal Node Input Source refs, single external
namespace, no namespace/node-id collision, acyclic, exactly one terminal/sink
Node) in a Pydantic `model_validator`, so any `GraphConfig` instance that
exists is structurally valid — there is no separate `validate()` step in the
API, and invalid configs are unrepresentable. We chose this because dr-graph
configs are optimizer genomes and identity/persistence inputs: downstream code
(hashing, execution, storage) should never have to ask "did anyone validate
this?", and invalid mutations should die loudly at construction. The accepted
cost is that tooling which needs to hold a broken config in memory (repair,
migration, partial editors) must work with raw dicts until it is fixed.
