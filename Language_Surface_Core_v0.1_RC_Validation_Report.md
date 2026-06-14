# ReasonScript Language Surface Core v0.1 RC

## Integrated Validation Report

Status: RELEASE CANDIDATE PASS

Validation date: 2026-06-14

## 1. Result

The integrated Language Surface path is fixed and validated:

```text
Source
  -> Surface AST
  -> Semantic AST
  -> Reason IR
  -> ExecutionPlan
```

Phase 1.1, 1.2, 1.3, and 1.6 contracts are covered by one RC conformance
suite and release gate. Equal source produces equal artifacts at every stage.

## 2. Exit Criteria

| Criterion | Result |
|---|---|
| Phase 1.1 | PASS |
| Phase 1.2 | PASS |
| Phase 1.3 | PASS |
| Phase 1.6 | PASS |
| Core RC Conformance | PASS, 8 tests |
| Full Regression | PASS, 188 tests, 1 skipped |
| Semantic AST Compatibility | PASS |
| Reason IR Compatibility | PASS |
| ExecutionPlan Compatibility | PASS |
| Serialization Compatibility | PASS |

## 3. Fixed Contracts

- immutable Surface AST;
- canonical `node_type` serialization;
- source order preservation;
- declaration and reference resolution;
- Transition statement placement;
- Calculation scope and terminal Result per execution path;
- deterministic Semantic AST projection;
- `reason-ir/0.1` schema compatibility;
- `execution-plan/0.1` schema compatibility.

## 4. Compatibility Decision

The Transition example in the RC summary omitted a state mapping. The
validated Phase 1.1 contract requires `from_state -> to_state`, so the
normative RC grammar retains that mapping. This avoids inventing an implicit
source State and preserves `AST-V006`.

No existing platform interface version is changed.

## 5. Release Artifacts

- `docs/ReasonScript_Language_Surface_Core_v0.1_RC.md`;
- `language_surface_core_conformance_tests/`;
- `release/language-surface-v0.1-rc/manifest.json`;
- `release/language-surface-v0.1-rc/run_release_validation.py`;
- this integrated report.

## 6. Verification

The integrated release gate completed successfully:

| Scope | Result |
|---|---|
| Phase 1.1 AST Mapping | PASS, 16 tests |
| Phase 1.2 Expression and Pattern | PASS, 18 tests |
| Phase 1.3 Statement | PASS, 16 tests |
| Phase 1.6 Calculation Integration | PASS, 16 tests |
| Core RC Conformance | PASS, 8 tests |
| Full Python regression | PASS, 188 tests, 1 skipped |
| HybridRuntime regression | PASS, 129 tests |
| Python bytecode compilation | PASS |
| Git whitespace validation | PASS |

The skipped Python test is an existing conditional adapter check. No release
criterion failed.
