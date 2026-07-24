# dr-graph API naming proposals

Naming problems surfaced while writing `.defs/vocab.html`. **Proposals only — do not
implement from a doc pass.** Golden/fixture files and hash values must never change from
these. Each item: current name, problem, proposed rename(s) with trade-offs, blast radius.

---

## 1. `NodeFieldSpec` → `NodeField` / `NodeFieldDef`

- **Current name:** `NodeFieldSpec` (in `spec.py`).
- **Problem:** Descendant of the retired `FieldSpec` spelling. The contract's vocabulary
  calls this a declared node input/output field, not a "Spec". The `-Spec` suffix reads as
  editorial coinage rather than the Node Output / declared-field vocabulary.
- **Proposed:** `NodeField` (matches "declared field" prose most directly) or `NodeFieldDef`
  (parallels `NodeDefinition` / `GraphDefinition`). Trade-off: `NodeField` is shortest and
  aligns with vocab, but is slightly less explicit that it is a declaration; `NodeFieldDef`
  keeps the `Def` family consistent at the cost of length.
- **Blast radius:** `spec.py`, `builders.py`, `definition.py`, `__init__.py` `__all__`,
  tests, fixtures, JSON schemas. No hash impact (field name of the type, not serialized data).

## 2. `spec` module → `config` module

- **Current name:** module `spec.py` holds `GraphConfig`, `NodeConfig`, `NodeFieldSpec`,
  `FieldRole`.
- **Problem:** The module name echoes the retired `GraphSpec` / `NodeSpec` era. The public
  types are now Config types; the module name mismatches the current vocabulary.
- **Proposed:** rename module to `config.py` (import-only change; the module name is not in
  `__all__`, so the public surface is unaffected). Trade-off: touches every internal import
  site and any test that imports from `dr_graph.spec` directly.
- **Blast radius:** internal imports across the package, tests importing `dr_graph.spec`.
  No public-API or hash impact.

## 3. `NodeConfig` vs. term "Node (Config)" — note, do not rename

- **Current name:** export `NodeConfig`; vocab term "Node (Config)" under umbrella "Node".
- **Problem:** term/name gap between the umbrella "Node" concept and the concrete
  `NodeConfig` export.
- **Proposed:** no rename. The contract explicitly does not require a class literally named
  `Node`, so `NodeConfig` is correct. Record the term/name gap in the vocab doc (already
  noted in the Node (Config) export row), not via an alias.
- **Blast radius:** none (documentation-only note).

## 4. `node_type` field — note, currently intentional

- **Current name:** `NodeConfig.node_type` (`StrictStr`), the open Node Definition reference.
- **Problem:** The vocabulary describes a typed Node Definition reference plus Identity Hash;
  `node_type` reads as a category label rather than a definition reference.
- **Proposed:** if a typed reference is ever modeled, rename to `node_definition_ref`.
  Currently intentionally open per README, so this is a term/name mismatch note only, not an
  action.
- **Blast radius:** if ever renamed — `spec.py`, builders, serialized field name (would
  change the identity payload and therefore every graph hash). Because it is identity-bearing,
  a rename here is a hash-breaking change and must be treated as a schema-version bump, never
  a silent rename.

## 5. `TerminalError` vs. `NodeError`

- **Current name:** `TerminalError` (`results.py`), a near-duplicate of `NodeError`'s shape
  restricted to the terminal node's error/blocked states.
- **Problem:** The name reads as a distinct error type rather than "the terminal node's
  outcome error", creating an asymmetry with `NodeOutcome` naming.
- **Proposed:** `TerminalOutcomeError`, or fold into the outcome types so the terminal case is
  expressed as a role of the per-node error rather than a sibling class. Trade-off: folding
  reduces surface but loses the explicit terminal-only type some callers may match on.
- **Blast radius:** `results.py`, `__init__.py` `__all__`, tests, any caller matching on the
  type. No hash impact.

## 6. `ClassifiedFailure` — Protocol under-described by its name

- **Current name:** `ClassifiedFailure` (`results.py`), a structural `Protocol` a `NodeError`
  is built from when a node raises.
- **Problem:** The name suggests a concrete failure value, but it is a diagnostics-shape
  protocol; the canonical failure-class strings live with the raising layer, not here. The
  name under-describes it as a structural contract.
- **Proposed:** `FailureDiagnosticsProtocol` or `FailureDiagnosticsShape`. Trade-off: longer,
  but signals "protocol / shape" and "diagnostics" rather than a concrete classified value.
- **Blast radius:** `results.py`, `__init__.py` `__all__`, tests, type annotations at call
  sites. No hash impact.

## 7. `graph_config_identity_payload` / `graph_config_identity_document` — verify they earn exports

- **Current names:** `graph_config_identity_payload`, `graph_config_identity_document`
  (`hashing.py`), the public Identity Payload and Identity Document builders.
- **Problem:** They are correctly named against the vocabulary, but only `graph_hash` is the
  headline identity operation; the two builders may be internal helpers that do not need to be
  in `__all__`.
- **Proposed:** verify each earns its export (a genuine bridge row a caller needs) rather than
  being an internal helper; if not needed publicly, drop from `__all__` (keeping the function).
  No rename proposed — the names are accurate.
- **Blast radius:** `__init__.py` `__all__`, docs (Graph Hash export row), any external caller.
  No hash impact.

## 8. `GraphValidationError` inside the `GraphExecutionError` taxonomy

- **Current name:** `GraphValidationError` subclasses both `GraphExecutionError` and
  `ValueError` (`errors.py`).
- **Problem:** A config-time validation failure is therefore also an "execution" error. The
  taxonomy conflates config-time validation with run-time execution, so callers cannot cleanly
  catch one without the other.
- **Proposed:** introduce a separate validation base (e.g. `GraphValidationError` rooted under
  a new `GraphConfigError` / validation base outside `GraphExecutionError`), leaving
  `GraphExecutionError` for run-time failures only. Trade-off: cleaner separation vs. one extra
  base class and a break for callers currently catching `GraphExecutionError` to cover both.
- **Blast radius:** `errors.py`, `__init__.py` `__all__`, tests asserting on the hierarchy,
  callers catching `GraphExecutionError`. No hash impact.
