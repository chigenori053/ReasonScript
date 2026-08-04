# ReasonScript Language Surface v0.5 Release & Feature Freeze

Specification ID: `reasonscript-language-surface/0.5`

Phase: LS-RELEASE-001

Status: Draft

Depends On:

- `reasonscript-language-surface/0.4`
- `pattern-identity-normalization/1.0`
- `range-pattern/1.0`

## Purpose

ReasonScript Language Surface v0.5 is the first feature-complete Language
Surface release. It freezes language syntax, semantic lowering, public
interfaces, and canonical branch semantics as a stable base for Runtime, SDK,
Playground, WorldModel, and MemorySpace work.

No new Language Surface feature is introduced by this specification.

## Feature Freeze

The following language areas are frozen:

- Module system: `module`, `package`, `import`, export, and visibility.
- Declarations: `fn`, `calculation`, `struct`, `enum`, `const`, and `let`.
- Type system: primitive, struct, enum, optional, and runtime types.
- Expressions: call, comparison, runtime call, and calculation expression.
- Statements: `return`, `if`, `match`, and loop family.
- Pattern system: literal, enum, optional, struct, nested struct, guard, OR, and range patterns.

The frozen semantic pipeline is:

```text
Language Surface
  -> Surface AST
  -> Semantic AST
  -> Reason IR
  -> ExecutionPlan
  -> Simulation
  -> Knowledge
```

## Frozen Public Interfaces

The following interfaces are frozen as the v0.5 compatibility surface:

- `reasonscript-language-surface/0.5`
- `parser/0.5`
- `reasonscript-ast/0.5`
- `reason-ir/0.5`
- `execution-plan/0.5`

Future revisions must preserve backward compatibility.

## Frozen Semantic Contracts

Pattern Identity is normative:

```json
{
  "pattern_identity": {
    "pattern_id": "...",
    "pattern_type": "...",
    "canonical_path": "..."
  }
}
```

Canonical path generation is deterministic. ExecutionPlan, Simulation, and
Knowledge preserve identical branch evidence and pattern identity for the
selected branch.

Pattern evaluation order is fixed:

```text
Pattern
  -> Pattern Identity
  -> Guard
  -> Branch Selection
  -> ExecutionPlan
  -> Simulation
  -> Knowledge
```

## Compatibility Policy

Patch releases in the `0.5.x` line may include bug fixes, performance
improvements, diagnostics, and compiler optimizations.

Patch releases must not change syntax, semantic meaning, IR schema, canonical
path generation, or Pattern Identity.

Major language extensions target Language Surface v0.6.

## Deferred Features

Pattern features deferred to v0.6 or later:

- Pattern Alias
- Tuple Pattern
- Array Pattern
- Map Pattern
- Rest Pattern
- Generic Pattern

Type system features deferred to v0.6 or later:

- Generic Types
- Trait Constraints
- Advanced Type Inference

Expression features deferred to v0.6 or later:

- Lambda
- Closure
- Async

## Required Validation

Before release, parser, AST, validation, semantic, pattern, Reason IR,
ExecutionPlan, Simulation, Knowledge, Playground audit, matrix, compatibility,
and regression suites must pass.

The pattern validation set includes literal, enum, optional, struct, nested
struct, guard, OR, and range patterns.

## Deliverables

- `docs/specs/reasonscript_language_surface_v0_5.md`
- `CHANGELOG.md`
- `RELEASE_NOTES_v0_5.md`
- `playground_language_surface_v0_5_audit.md`
- `playground_language_surface_v0_5_matrix.json`
- `tests/compatibility/test_language_surface_v0_5.py`

## Release Criteria

Language Surface v0.5 is releasable when all listed features are implemented,
all frozen public interfaces are documented, compatibility and regression tests
pass, Playground audit reports `PASS`, Pattern Identity is deterministic across
repeated compilation, and no planned v0.5 language feature remains
unimplemented.

## Development Policy After v0.5

After this release, Language Surface enters maintenance mode. Development
priority shifts to Runtime, SDK, Playground IDE, WorldModel, and MemorySpace.

New language constructs should not be added to the v0.5 branch unless they fix
correctness or compatibility issues. New syntax and language features target
the next language version, v0.6.
