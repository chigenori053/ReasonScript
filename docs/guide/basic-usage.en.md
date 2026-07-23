# ReasonScript Basic Usage

Audience: engineers who have read `docs/guide/concepts.en.md` and now need to
write, compile, and run ReasonScript source. This document is a practical
walkthrough of the Language Surface v0.1 syntax plus the incremental v1.0
extensions (functions, enums, structs, optionals) that ship in this
repository, and of the `reason` toolchain. It is intentionally example-driven;
for the normative rules behind each construct, follow the cross-references to
`docs/`.

Every code sample below is either taken verbatim from, or is a minimal
variant of, a file that already exists and is validated in this repository
(`examples/`, `hello_world/`, `tests/`).

## 1. Toolchain and Project Layout

A ReasonScript package is a directory with a `reason.toml` manifest:

```toml
[package]
name = "hello_world"
version = "0.1.7"

[compiler]
language_core = "0.7"
platform = "0.2"

[runtime]
backend = "RuntimeReal"
```

Conventional layout (`hello_world/`):

```text
hello_world/
├── reason.toml
├── src/
│   └── main.rsn
└── tests/
    └── sample_test.rsn
```

Every `.rsn` file that belongs to a package starts with a `package` statement
naming its package:

```reasonscript
package hello_world
module main {
    fn run(goal) {
        return goal
    }
}
```

### CLI commands

The `reason` CLI (`./reason <command>`, or `python3 -m toolchain <command>`
from the repository root) drives the pipeline described in
`docs/guide/concepts.en.md` Section 4:

| Command | Effect |
|---|---|
| `reason init <name>` | Scaffold a new package directory |
| `reason build [--package <name>]` | Parse and compile sources to Reason IR / ExecutionPlan |
| `reason check [--package <name>]` | Validate sources without producing build artifacts |
| `reason run [--package <name>]` | Build, then execute against a Runtime, producing an InferenceResult |
| `reason test [--package <name>]` | Run the package's test sources |

Multi-package workspaces are declared with a `reason.workspace.toml` at the
workspace root; `--package` selects one member package, and dependency
ordering across the workspace is resolved topologically (see
`docs/ReasonScript_Toolchain_Phase_2_Report.md`).

## 2. Modules and Imports

`module` is the unit of namespacing. A file may declare one or more modules;
`pub` controls whether the module's public symbols are importable from
elsewhere.

```reasonscript
module finance {
}

pub module finance {
}
```

Imports resolve either a whole module or a single symbol, with an optional
alias:

```reasonscript
import finance.loan
import finance.loan as loan
import finance.RiskScore
import finance as loan
import finance.RiskScore as risk
```

Unqualified name lookup, in precedence order:

1. Local bindings inside the current `calculation`
2. The current module's own namespace
3. Public symbols brought in by `import`

Two imports that would expose the same unqualified name are a compile error
(`NS-040`), as is importing a private symbol (`NS-050`) or a name that does
not exist (`NS-020`/`NS-030`). Qualify a name explicitly with `::` when you
need to disambiguate or reference across modules:

```reasonscript
finance::RiskScore
loan::RiskScore
```

Reference: `docs/ReasonScript_Language_Surface_Namespace_Import_Resolution_v0.1.md`.

## 3. Declarations and Relations

Every SemanticUnit type from the Semantic Language Core (see
`docs/guide/concepts.en.md` Section 3) has a matching declaration keyword:
`Concept`, `Object`, `Event`, `Action`, `Attribute`, `Goal`, `Constraint`.
These are declared inside a `module` body and named.

Relations connect two declarations that resolve within the **same module**:
`IsA`, `PartOf`, `Cause`, `Dependency`, `Constraint`, `Temporal`, `Spatial`,
`Similar`.

Reference: `docs/ReasonScript_Language_Surface_Core_v0.1_RC.md` Section 3.

## 4. Transitions

A `transition` block declares a state change the planner may select. It maps
an initial declaration to a target one, optionally guards it with
`require`, and annotates or targets a `Goal`:

```reasonscript
transition Approve {
    Draft -> Approved
    require Adult
    goal LoanApproval
    reach LoanApproval
}
```

Allowed statements inside a `transition` body: `Require`, `Goal`, `Reach`,
`If`, `Match`, and expression (call) statements. `require` resolves to a
`Constraint`; `goal` and `reach` resolve to a `Goal`. The last top-level
`reach` in the body determines the semantic Transition's target — this is a
compile-time mapping only, Goal *satisfaction* is decided at execution by
Operational Semantics (`docs/guide/concepts.en.md` Section 5).

## 5. Calculations

A `calculation` is the executable, expression-oriented counterpart of a
`transition` — a named block of statements with immutable local bindings that
must terminate in exactly one `result`:

```reasonscript
calculation RiskScore {
    result = income * factor
}

pub calculation RiskScore goal: RiskEvaluation {
    let score = income * factor
    result = score
}
```

`pub` makes the calculation importable; the optional `goal: <Goal>` annotation
attaches it to a declared `Goal`. Each statement in the body compiles to one
ordered semantic Transition:

| Statement | Semantic projection |
|---|---|
| `let` | expression-specific Transition (state-variable step) |
| assignment (`x = ...`) | `StateUpdateTransition` |
| bare expression (must be a call) | `CallTransition` |
| `if` / `match` | `DecisionTransition` |
| `result = ...` | `ResultTransition` (to the calculation's semantic Goal) |

Reference: `docs/ReasonScript_Language_Surface_Calculation_Integration_v0.1.md`,
`docs/ReasonScript_Language_Surface_Statement_v0.1.md`.

## 6. Statements

The full statement hierarchy, and where each is legal:

```text
StatementNode
├─ LetStatementNode          let score = 100
├─ AssignmentStatementNode   score = score + 1     (Calculation body only)
├─ ResultStatementNode       result = score         (Calculation body, exactly once, final)
├─ RequireStatementNode      require Adult          (Transition body)
├─ GoalStatementNode         goal LoanApproval       (Transition body)
├─ ReachStatementNode        reach LoanApproval      (Transition body)
├─ ExpressionStatementNode   publish(order)          (root must be a call)
├─ IfStatementNode           if / elif / else
└─ MatchStatementNode        match { pattern => ... }
```

Placement rules:

| Container | Allowed statements |
|---|---|
| Module body | declarations, imports, relations, `transition`, `calculation` |
| Transition body | Require, Goal, Reach, If, Match, ExpressionStatement |
| Calculation body | Let, Assignment, If, Match, ExpressionStatement, Result |

`if` / `elif` / `else`:

```reasonscript
if score > 80 {
    reach Approved
} elif score > 50 {
    reach Review
} else {
    reach Rejected
}
```

`result` must be the final top-level statement of a `calculation` body and
must appear exactly once; it is never legal inside a nested `if`/`match` arm
or inside a `transition` body. Statement order is preserved end-to-end
(parsing, serialization, semantic projection) because it determines the
generated Transition sequence.

Reference: `docs/ReasonScript_Language_Surface_Statement_v0.1.md`.

## 7. Types

Type annotations are validation-only in Language Surface v0.1 — they do not
define runtime object layout, and there is no generic/trait/inheritance
system:

```reasonscript
let age: Int = 20
let score: Float = 0.8

calculation RiskScore -> Float {
    result = score
}
```

Primitive types: `Int`, `Float`, `Bool`, `String`, `Null`. A State type
annotation names one of the SemanticUnit kinds and requires the referenced
declaration to be of that kind:

```reasonscript
let target: Goal = LoanApproval
let rule: Constraint = Adult
```

Compatibility rules worth remembering: arithmetic requires two operands of
the *same* numeric type (`Int + Float` is invalid — cast explicitly at the
call site if you need mixed arithmetic), comparisons require equal known
types, and logical operators require `Bool` operands.

Reference: `docs/ReasonScript_Language_Surface_Type_Specification_v0.1.md`.

## 8. Expressions

Literals: integers (`42`), floats (`3.14`), booleans (`true`/`false`),
strings (`"hello"`), `null`. Negative numbers parse as unary negation
(`-score` is `Negate(score)`), not a negative literal token.

Operators, highest precedence first:

| Level | Constructs |
|---:|---|
| 80 | member access (`a.b`), call (`f(x)`) |
| 70 | unary `-`, unary `!` |
| 60 | `*` `/` `%` |
| 50 | `+` `-` |
| 40 | `==` `!=` `>` `>=` `<` `<=` |
| 30 | `&&` |
| 20 | `\|\|` |

All binary operators are left-associative; parentheses are preserved through
serialization, not just parsed away:

```reasonscript
1 + 2 * 3        // Binary(Add, 1, Binary(Multiply, 2, 3))
(a + b)          // Parenthesized(Binary(Add, a, b))
user.profile.age // nested MemberAccess
risk(score, age) // Call(risk, [score, age])
```

Reference: `docs/ReasonScript_Language_Surface_Expression_Pattern_v0.1.md`.

## 9. Functions

`fn` declares an ordinary, module-level function. Parameters and the return
type are mandatory (`FN-002`, `FN-003`); direct recursion is rejected in
v1.0 (`FN-007`).

```reasonscript
module Basic {
    fn Value() -> int {
        return 42
    }

    calculation Result {
        result = Value()
    }
}
```

As of the Structured Function Control Flow extension (FSI-2), a function body
is no longer limited to a single terminal `return` — it may branch, as long
as **every reachable path** ends in a `return`:

```reasonscript
fn Score(color: Color, shape: Shape) -> int {
    match color {
        Color.Red => {
            match shape {
                Shape.Circle => return 10
                Shape.Square => return 20
            }
        }
        Color.Blue => return 0
    }
}
```

Reference: `docs/specs/function_semantic_integration_v1.md`,
`docs/specs/function_control_flow_v1.md`.

## 10. Match, Patterns, and Structured Data

`match` is legal in `transition`, `calculation`, and `fn` bodies. The
supported v0.1 patterns are identifiers, `_` (wildcard), and literals:

```reasonscript
match state {
    Draft => approve()
    Approved => publish()
    _ => reject()
}
```

The v1.0 extensions add pattern forms used throughout `tests/`:

**Enums** — declare variants, match them qualified (`Type.Variant`):

```reasonscript
module Basic {
    enum Color {
        Red
        Blue
    }

    fn Get() -> Color {
        return Red
    }
}
```

**Structs** — declare fields, match with literal fields, bound fields, or
nested struct fields:

```reasonscript
module Test {
    struct Position { x: int, y: int }
    struct Person { position: Position }

    fn Score(person: Person) -> int {
        match person {
            Person { position: Position { } } => return 1
        }
    }

    calculation Result {
        result = Score(Person { position: Position { x: 1, y: 2 } })
    }
}
```

**Optionals** — `optional<T>`, matched with `some(x)` / `none`:

```reasonscript
fn Score(value: optional<int>) -> int {
    match value {
        some(x) => return x
        none => return 0
    }
}
```

**Or-patterns and `default`** — combine alternatives, or fall through:

```reasonscript
fn Score(value: int) -> int {
    match value {
        1 | 2 | 3 => return 10
        default => return 0
    }
}
```

**Guards** — restrict a bound-field match with a boolean condition using
`when`:

```reasonscript
match point {
    Point { x } when x > 0 => return 1
    Point { } => return 0
}
```

Reference: `docs/specs/enum_symbol_resolution_v1.md`,
`docs/specs/struct_pattern_matching_v1.md`,
`docs/specs/optional_pattern_matching_v1.md`,
`docs/specs/or_pattern_v1.md`, `docs/specs/pattern_guard_v1.md`.

## 11. A Complete Worked Example

Combining a function and a calculation that calls it (from
`examples/function_call_from_calculation.rsn`):

```reasonscript
module Basic {

    fn Value() -> int {
        return 42
    }

    calculation Result {
        result = Value()
    }

}
```

Running it:

```sh
reason check    # parse + validate only
reason build    # compile to Reason IR / ExecutionPlan
reason run      # execute against the configured Runtime backend, print InferenceResult
```

## 12. The Original Core Primitives

Before the block-structured Language Surface, ReasonScript defined a minimal
line-based core (still valid, still parsed — `docs/grammar.md`) built around
six primitives, useful for understanding the language's proof/rollback model
in isolation:

```reasonscript
goal preserve_session_consistency
derive identify_transition_gap
prove deterministic_state_transition
apply patch_session_machine
converge verify_repl_stability
rollback previous_safe_state
```

| Primitive | Payload type | Meaning |
|---|---|---|
| `goal` | Symbol | declare the desired state |
| `derive` | Symbol | generate a candidate reasoning strategy |
| `prove` | Proof | validate a derivation; a `Proof` whose text contains `invalid` is a deterministic failure that triggers automatic `rollback` |
| `apply` | State | commit a verified change |
| `converge` | Symbol | stabilize on a label |
| `rollback` | State | revert to the named safe checkpoint |

`apply`'s payload is classified, in order, as rational (`1/2`), signed
integer (`-3`), natural number (`42`), or symbol (`x`). Each statement is a
single line; unknown keywords are ignored by the current parser; blocks,
comments, and strings are out of scope for this core form.

Reference: `docs/semantics.md`, `docs/grammar.md`.

## 13. Validation and Conformance

Before relying on new syntax, run the layer-specific regression suite (each
spec document lists its own command) or the full suite:

```sh
python3 -m pytest --import-mode=importlib
```

For release-gated guarantees (Language Surface v0.1, Semantic Language v0.2,
Platform v0.1 Alpha), run the corresponding gate under `release/`, e.g.:

```sh
python3 release/language-surface-v0.1/run_release_validation.py
python3 release/semantic-language-v0.2/run_release_validation.py
python3 release/v0.1-alpha/run_release_validation.py
```

## 14. Where to Go Next

- Conceptual model (Reasoning Space, Knowledge, determinism guarantees):
  `docs/guide/concepts.en.md`.
- Full grammar: `docs/grammar.md`, `docs/ReasonScript_Language_Surface_Core_v0.1_RC.md`.
- Statement, expression, and type contracts: the LS-1/1.2/1.3 documents in
  `docs/ReasonScript_Language_Surface_*`.
- Incremental v1.0 features (functions, enums, structs, optionals, guards,
  timezone-aware timestamps): `docs/specs/`.
- Execution semantics and Runtime contract: `docs/ReasonScript_Operational_Semantics_v0.1.md`.
