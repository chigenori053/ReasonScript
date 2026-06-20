# SDK Review Report

Classification: Partially Complete

Scope: Runtime SDK, ReasonGraph SDK, and ExecutionPlan SDK.

## Findings

- SDK-001: SDK boundaries are mostly clear. ReasonGraph and ExecutionPlan SDKs
  have separate builder, query, and validation surfaces; runtime SDK re-exports
  integration primitives.
- SDK-002: Immutable guarantees are preserved in DTO-oriented model surfaces and
  builder outputs where used. Some Python convenience layers still expose normal
  mutable containers at the edges.
- SDK-003: Builders and validators are complete for Phase 1 fixture coverage,
  but they do not yet express every cross-layer invariant needed by Beta.

## Architectural Gaps

- Shared SDK version metadata.
- Clear split between stable SDK API and internal conformance helpers.
- Cross-SDK trace and diagnostic conversion helpers.

## Recommendations

- Define SDK public API manifests before Beta.
- Keep builders deterministic and validators side-effect free.
- Add compatibility tests across Runtime SDK, ReasonGraph SDK, and
  ExecutionPlan SDK.
