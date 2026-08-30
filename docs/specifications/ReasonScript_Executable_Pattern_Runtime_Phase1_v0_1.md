# ReasonScript Executable Pattern Runtime — Phase 1 v0.1

Status: ACCEPTED

## Purpose

Phase 1 closes the gap between Surface-valid pattern syntax and the executable
ReasonScript runtime. Programs accepted by the default executable check may use
enum values, Optional values, and `match` statements without failing during
Computation IR lowering or native execution.

## Runtime values

- `Enum.Variant` is a first-class value identified by both enum and variant
  name. Equality compares both names.
- `some(value)` is a first-class Optional value.
- `none` is the empty Optional value and is distinct from `null`.
- Native JSON results encode these values as tagged objects:
  `{"enum":"Color","variant":"Red"}`,
  `{"optional":"some","value":...}`, and `{"optional":"none"}`.

## Match execution

`match` evaluates its subject once and tests arms in source order. The first
matching arm whose guard evaluates to true executes. Pattern bindings are
available to that guard and arm body and do not escape the arm.

The executable pattern vocabulary is:

- identifier binding, wildcard, and `default`;
- literal and numeric range patterns;
- enum variants;
- `some(binding)`, nested `some(pattern)`, and `none`;
- struct field patterns, including shorthand field bindings;
- or-patterns with the binding compatibility already enforced by Surface
  validation.

Surface exhaustiveness validation remains authoritative. If malformed raw IR
reaches a match with no selected arm, execution fails with `RT-MATCH-001`.

## Computation IR contract

The additive `reason-computation-ir/0.1` vocabulary gains:

- expressions `enum_value`, `optional_some`, and `optional_none`;
- terminator `pattern_branch`, containing a subject expression, a declarative
  pattern, and `then`/`else` block targets.

Both the temporary Python interpreter and the canonical Rust host must decode
and execute the same representation. Existing IR documents remain valid.

## Compatibility and exclusions

This phase does not add string concatenation, dynamic arrays, recursion,
cross-file runtime linking, or new source syntax. It does not change existing
Surface diagnostics or exhaustiveness rules. `null` behavior is preserved;
only the formerly conflated `none` value receives distinct runtime semantics.

## Validation gates

- enum construction, equality, and enum match parity;
- Optional construction and match parity;
- literal, range, struct, nested, guarded, and or-pattern parity;
- Python IR/Rust host result and error-code parity;
- official examples `008_struct_pattern.rsn` and `009_optional_match.rsn`
  pass default executable check and build/run validation;
- workspace, diagnostics, artifacts, golden tests, and canonical `reason ci`.
