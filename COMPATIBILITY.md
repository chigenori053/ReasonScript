# Compatibility

ReasonScript is pre-1.0 (`0.1.0-alpha`, see [VERSION](VERSION)). This
document tracks which interfaces are frozen (safe to build against), which
are still moving, and the subsystem maturity classification used to reason
about Beta readiness. See [GOVERNANCE.md](GOVERNANCE.md#decision-making) for
how changes to frozen interfaces are approved.

## Versioning Policy

Individual layers of the platform are versioned and frozen independently
(e.g. `parser/0.1`, `reason-ir/0.1`) rather than the project having one
global semantic version. A layer version freeze means:

- The wire format / schema / public surface for that layer will not change
  within the same version number.
- Breaking changes require a version bump of that specific layer, called
  out in [CHANGELOG.md](CHANGELOG.md).

There is not yet a platform-wide compatibility matrix connecting these
per-layer versions — this is a tracked Beta P0 gap (see
[ROADMAP.md](ROADMAP.md#beta-planning) and
`docs/platform_architecture_review/versioning_strategy_report.md`).

## Frozen Interfaces

| Interface | Version | Frozen | Notes |
| --- | --- | --- | --- |
| `reason-ir/0.1` | 0.1 | 2026-06-13 | Reason IR JSON ABI, schema at `schemas/reason_ir.schema.json` |
| `reasonscript-ast/0.1` | 0.1 | 2026-06-13 | Semantic AST |
| `parser/0.1` | 0.1 | 2026-06-13 | Source -> Surface AST |
| `compiler/0.1` | 0.1 | 2026-06-13 | AST -> Reason IR |
| `transaction/0.1` | 0.1 | 2026-06-13 | Prepare -> Validate -> Commit -> StateDelta protocol |
| `common-dto/0.1` | 0.1 | 2026-06-13 | Rust, Python, TypeScript, Go, Java bindings under `dto/` |
| `conformance-framework/0.1` | 0.1 | 2026-06-13 | `conformance/` layered certification |
| `reasonscript-language-surface/0.1` | 0.1 | 2026-06-14 | Modules, imports, declarations, patterns, statements, Calculations |
| `execution-plan/0.1` | 0.1 | 2026-06-14 | Immutable planner output |
| `reasonscript-calculation-semantics/0.1` | 0.1 | 2026-06-14 | Calculation blocks |
| `reasonscript-semantic-language/0.2` (Core) | 0.2 | 2026-06-15 | SemanticUnit/SemanticRelation/Reasoning Space/SemanticPlan/SemanticSimulation |

See [CHANGELOG.md](CHANGELOG.md) for the release notes behind each freeze
and `release/*/manifest.json` for the machine-readable interface list and
per-language binding status of each release gate.

## Subsystem Maturity

Classification from the Platform Architecture Review v1.0
(`docs/platform_architecture_review/platform_architecture_v1.md`):

| Subsystem | Classification |
| --- | --- |
| Language | Partially Complete |
| Runtime | Partially Complete |
| Execution Architecture | Partially Complete |
| Toolchain | Partially Complete |
| SDK | Partially Complete |
| World Model SDK | Partially Complete |
| LSP | Partially Complete |
| IDE | Partially Complete |
| Cross-Layer Architecture | Requires Refactoring |
| ReasoningTrace | Missing (proposal only) |
| Versioning | Requires Refactoring |

"Cluster Runtime" and a standalone "Tensor Runtime" product are not present
in this table because they are not implemented; see
[docs/architecture/cluster-runtime.md](docs/architecture/cluster-runtime.md)
and [docs/architecture/tensor.md](docs/architecture/tensor.md) for exactly
what exists today versus what is aspirational.

## Known Limitations (current alpha)

- Distributed Runtime, persistence, and event sourcing are not implemented.
- Macros, a formatter, and an optimizer are not implemented.
- Multi-package dependency resolution and a package registry are not
  implemented (`reason build`/`run`/`test`/`check` are single-workspace).
- Go conformance is not exercised in CI-equivalent environments without a Go
  toolchain; Java DTO bindings compile but lack a JSON codec adapter.
- No sandboxing or capability-scoped execution exists yet — see
  [SECURITY.md](SECURITY.md#known-limitations).

## Beta Readiness

Not Beta-ready. Beta requires four platform contracts to land first:
platform diagnostics, `ReasoningTrace`, a Toolchain package graph, and
`ExecutionScope`/`CallStack` semantics. Tracked in
[ROADMAP.md](ROADMAP.md#beta-planning).
