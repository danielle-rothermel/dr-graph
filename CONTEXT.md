# dr-graph

dr-graph describes computation graphs as hashable spec data, validates them
structurally, executes them purely and deterministically via an injected
callback, and gives each graph a canonical identity via digest — nothing else.
The searched-over layer (specs) is data; the searching layer (optimizers,
durable workflows) is caller code, and durability, retries, scheduling,
persistence, prompts, and providers belong to callers.

## Language

**Graph Spec**:
A hashable data description of a computation graph — a set of nodes plus a
designated terminal node, structurally valid by construction (an invalid
Graph Spec cannot exist). The unit that is stored, searched over, and
identified by digest.
_Avoid_: treatment, treatment-description graph, workflow, pipeline

**Binding Ref**:
A reference in a node's input bindings naming where an input value comes
from — another node's output (`encoder.description`) or an external input
(`task.prompt`).
_Avoid_: edge, wire, pointer

**Parameters**:
A node's open, digest-covered configuration values, interpreted solely by the
caller's run-node callback — the interpreter never reads them. The only open
dict on a node; identity-irrelevant data lives outside the spec, keyed by
digest.
_Avoid_: metadata, options

**Digest**:
The canonical identity of a Graph Spec — a hash covering every byte of the
spec. Two specs with different bytes are different treatments, always.
_Avoid_: hash, id, fingerprint

**External Input**:
A value supplied by the caller at execution time rather than produced by a
node, referenced under the reserved `task` namespace. `task` is the ref-file
spelling; the concept is external.
_Avoid_: task input

**Inlined Subgraph**:
A subgraph composed into a parent by flattening: its nodes renamed under a
prefix and rewired, leaving an ordinary Graph Spec with no remaining
subgraph boundary.
_Avoid_: nested graph, sub-workflow, child graph

**Treatment**:
Whetstone-ai's word for what its graph specs represent (an experiment
condition). A use-case term, not dr-graph vocabulary — dr-graph code and docs
say Graph Spec.
