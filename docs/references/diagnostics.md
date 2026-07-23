# Diagnostics Reference

ReasonScript's compiler frontend (`frontend/language_surface/`,
`frontend/ast/`) raises structured diagnostics with stable codes during
`reason build` and `reason check` (see
[docs/architecture/compiler.md](../architecture/compiler.md)). This page is
the first consolidated index of those codes — it's generated from the
diagnostic strings actually raised in the compiler source, grouped by the
language area each prefix covers. Some diagnostics carry two codes
(an older and a newer numbering scheme still present side by side in the
source, e.g. `"NS-001 NS-V002 duplicate module namespace"`) — both are
listed together where that happens.

If a diagnostic you hit isn't listed here, treat this page as incomplete
rather than authoritative — the underlying error message from `reason
build`/`check` is always the source of truth.

## Namespace / Imports (`NS-*`)

| Code | Meaning |
| --- | --- |
| `NS-001` / `NS-V002` | Duplicate module namespace, or duplicate symbol within a namespace |
| `NS-020` / `NS-V003` | Import target does not exist |
| `NS-021` / `NS-V004` | Alias conflicts with an existing name |
| `NS-030` / `NS-V005` | Qualified target does not exist, or a qualified path/identifier is malformed |
| `NS-040` / `NS-V007` | Ambiguous imported or qualified symbol |
| `NS-050` / `NS-V006` | Module exports no public symbols, or a private symbol was imported |

See [ReasonScript_Language_Surface_Namespace_Import_Resolution_v0.1.md](../specifications/ReasonScript_Language_Surface_Namespace_Import_Resolution_v0.1.md).

## Functions (`FN-*`)

| Code | Meaning |
| --- | --- |
| `FN-001` | Invalid statement in function body, duplicate function symbol, or invalid visibility |
| `FN-002` | Missing parameter type annotation |
| `FN-005` | Argument count or type mismatch on a function call, or return type mismatch |
| `FN-006` | Duplicate parameter name |
| `FN-007` | Recursive function calls are rejected |
| `FN-020` | Undefined assignment target inside a function body |
| `FN-021` | Duplicate variable binding |

## Function Control Flow (`FCF-*`)

| Code | Meaning |
| --- | --- |
| `FCF-001` | Not all execution paths return a value |
| `FCF-002` | Unreachable statement |
| `FCF-004` | Condition in an `if`/guard must be `Bool` |

See [function_control_flow_v1.md](../specifications/function_control_flow_v1.md).

## Calculations (`CAL-*`)

| Code | Meaning |
| --- | --- |
| `CAL-001` | Invalid statement kind in a calculation body |
| `CAL-010` | Calculation requires a terminal `result` statement |
| `CAL-011` | Multiple `result` statements on one path |
| `CAL-012` | `result` must be the final statement |
| `CAL-020` | Undefined variable or assignment target |
| `CAL-021` | Duplicate binding |
| `CAL-030` | Dependency cycle detected between calculation bindings |

## Statements (`ST-*`)

| Code | Meaning |
| --- | --- |
| `ST-001` | Malformed `let`/`const` identifier |
| `ST-002` | Malformed `let`/`const` expression |
| `ST-003` | Duplicate binding |
| `ST-020` | Malformed `result` statement expression |
| `ST-030` | Referenced constraint does not exist |
| `ST-031` / `TYPE-010` / `TYPE-V008` | A `require` reference must resolve to a `Constraint` |
| `ST-060` | An expression statement's root must be a call expression |
| `ST-071` | `if` statement requires a body |
| `ST-081` | Match arm requires a body |

## Types (`TYPE-*`)

| Code | Meaning |
| --- | --- |
| `TYPE-010` / `TYPE-V008` | `require` reference is not a `Constraint` |
| `TYPE-011` / `TYPE-V007` | A goal/`reach` reference is not a `Goal` |

See [docs/language/type-system.md](../language/type-system.md).

## Pattern Matching (`MT-*`, `PT-*`, `PG-*`, `OP-*`, `OPM-*`, `SP-*`, `SPM-*`, `NP-*`, `ESR-*`)

| Code | Meaning |
| --- | --- |
| `MT-001` / `MT-002` | Malformed `match` expression, or a `match` with no arms |
| `PT-001` / `MSI-001` | Duplicate pattern |
| `PT-002` / `MSI-002` | `default` arm is not last |
| `PT-003` / `MSI-003` | Multiple `default` arms |
| `PT-004` | Undefined identifier used as a pattern |
| `PT-005` | Literal type mismatch in a pattern |
| `PT-006` | Duplicate wildcard pattern |
| `PT-007` | Unreachable pattern (shadowed by an earlier arm) |
| `PT-009` | Undefined namespace in a qualified pattern |
| `PT-010` / `ESR-001` | Undefined enum variant |
| `PT-011` | Ambiguous qualified symbol |
| `PT-201`/`PT-203`/`PT-204`/`PT-206` | Guard/range/destructuring/nested patterns not supported at a given language-surface index level (`LSI-200`) |
| `PG-001` | Malformed guard, or guard expression is not `Bool` |
| `OP-001` | Or-pattern requires at least one alternative |
| `OP-002` | Alternatives bind incompatible variable sets |
| `OP-003` | Incompatible or-pattern alternative categories |
| `OP-004` | Duplicate or-pattern alternative |
| `OPM-002` / `OPM-003` | Optional pattern used against a non-optional match value |
| `SP-001` / `SP-103` | Duplicate struct field in a pattern |
| `SP-002` / `NP-002` / `NP-003` | Invalid struct pattern syntax (including a missing closing brace) |
| `SP-101` | Undefined struct type in a pattern |
| `SP-102` | Unknown struct field referenced |
| `SP-104` | Field type mismatch |
| `SP-105` | Required field missing from the pattern |
| `SP-106` | Duplicate semantic field symbol |
| `SPM-005` | Duplicate binding name in a struct field pattern |
| `NP-010` | Nested pattern depth exceeded |
| `ESR-001`..`ESR-004` | Unknown enum / unknown variant / variant referenced unqualified |

See [docs/language/syntax.md#pattern-matching](../language/syntax.md#pattern-matching)
and the individual specs under `docs/specifications/*_v1.md` for the
normative rule behind each code family.

## Expressions (`EX-*`)

| Code | Meaning |
| --- | --- |
| `EX-001` | Malformed identifier expression |
| `EX-201A-001` | Duplicate field in a struct literal |
| `EX-201A-002` | Invalid struct literal syntax |

## How Diagnostics Surface

- `reason check` reports diagnostics without producing build artifacts —
  the fastest way to iterate.
- `reason build` reports the same diagnostics and stops before writing to
  `target/` if any are raised.
- The LSP (`frontend/lsp/`) surfaces the same diagnostics inline in an
  editor — see [docs/guides/ide.md](../guides/ide.md).

## Runtime-Level Failures

Diagnostics above are compile-time. At runtime, a rejected or failed
execution reports through `InferenceResult` as one of `completed`,
`rejected`, `decision_required`, or `failed` — see
[docs/language/semantics.md](../language/semantics.md#the-ten-operational-semantics-rules-os-01os-10).
