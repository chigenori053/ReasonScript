# Compiler

The Compiler is the Python frontend that turns `.rsn` source text into
Reason IR — the versioned JSON contract that everything downstream
(runtimes, SDKs, tooling) is built against. It is entirely separate from the
Rust runtime crates; there is no shared process boundary until Reason IR is
produced.

## Pipeline

```text
Source (.rsn)
  -> Surface AST      frontend/language_surface/
  -> Semantic AST     frontend/ast/
  -> Reason IR        frontend/compiler/compiler.py
```

### 1. Surface AST — `frontend/language_surface/`

The parser-facing layer, close to concrete syntax:

- `lexer.py`, `parser.py` — tokenize and parse `.rsn` source.
- `nodes.py` — Surface AST node types: `GoalNode`, `ConceptNode`,
  `EventNode`, `AttributeNode`, `FunctionDeclarationNode`, and the rest of
  the module/function/pattern surface grammar (see
  [docs/language/syntax.md](../language/syntax.md)).
- `expressions.py` — expression parsing.
- `namespace.py` — module namespace, import, and qualified-name resolution
  (see [Namespace/Import spec](../specifications/ReasonScript_Language_Surface_Namespace_Import_Resolution_v0.1.md)).
- `pattern_evaluator.py` / `pattern_decision.py` — match/pattern semantics
  (or-patterns, guards, struct patterns — see the individual specs under
  `docs/specifications/*_v1.md`).
- `validation.py` — Surface-level structural validation.
- `integration.py` — the public entry points: `compile_program`,
  `project_module`, `project_program`, `execution_plan_for`.

### 2. Semantic AST — `frontend/ast/`

The canonical, normalized AST that the rest of the platform is built on:

- `nodes.py` — canonical node types.
- `mapping.py` — Surface AST -> Semantic AST projection (see
  [AST Mapping spec](../specifications/ReasonScript_Language_Surface_AST_Mapping_v0.1.md)).
- `validation.py` — canonical AST validation (`AST_Validation_Specification_v0.1.md`,
  `AST_Schema_Validation_Specification_v0.1.md`).

### 3. Reason IR — `frontend/compiler/compiler.py`

`compile()` runs, in order:

1. `validate_ast` — reject malformed Semantic AST early.
2. `expand_defaults` (`expander.py`) — fill in default values.
3. `inject_policies` (`injector.py`) — attach `CompilationPolicies`
   (execution policy, trace policy, planner policy).
4. `lower()` (`lowering.py`) — build the Reason IR document: `initial_state`,
   `goal`, `transitions`, `constraints`, `context_refs`, `policies`.
5. Validate the result against `schemas/reason_ir.schema.json`.

The output is plain JSON conforming to the frozen `reason-ir/0.1` contract
(see [COMPATIBILITY.md](../../COMPATIBILITY.md)). This is intentional: any
language or tool with a JSON parser can consume Reason IR without linking
against the Python frontend, which is why `dto/` ships bindings for Rust,
Python, TypeScript, Go, and Java, and why a separate Rust validator exists
(`HybridRuntime/src/bin/reason-ir-validator.rs`).

## From Reason IR to ExecutionPlan

Reason IR is a *planning request*, not something directly executable. A
planner (governed by the injected `planner policy`) selects a deterministic
`ExecutionPlan` from the candidate `Transition`s in the IR: minimum
expected cost is the primary key, with `(total cost, step count,
transition_id sequence)` as the full deterministic tie-break (see
[Operational Semantics OS-06](../specifications/ReasonScript_Operational_Semantics_v0.1.md)).
An `ExecutionPlan`, once produced, is immutable — see
[runtime.md](runtime.md) for what happens to it next.

## Tooling Built on the Compiler

- **LSP** (`frontend/lsp/`) reuses the parser for diagnostics but currently
  keeps a separate lightweight source index, because the AST does not yet
  carry source spans — a known gap tracked in
  `docs/platform_architecture_review/lsp_review.md` and
  [ROADMAP.md](../../ROADMAP.md).
- **IDE core** (`frontend/ide/`) is editor-agnostic and currently shells out
  to the `reason` CLI commands rather than calling the compiler in-process.
- **`reason build`/`check`** (`toolchain/`) drive `compile_program` /
  `project_program` directly; see
  [docs/references/cli.md](../references/cli.md).

## Legacy Note

[`docs/specifications/grammar.md`](../specifications/grammar.md) and
[`docs/specifications/semantics.md`](../specifications/semantics.md)
describe an early, minimal single-line grammar (`goal`/`derive`/`prove`/
`apply`/`compute`/`converge`/`rollback`). That grammar predates and is much
smaller than the current Language Surface (modules, functions, structs,
enums, pattern matching). Treat those two documents as historical
foundations, not the current syntax — see
[docs/language/syntax.md](../language/syntax.md) for the current grammar.
