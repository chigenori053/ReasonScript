# ReasonScript Language Surface v0.1 Release Validation Report

Status: RELEASED

Release date: 2026-06-14

Version: `reasonscript-language-surface/0.1`

## 1. Release Decision

ReasonScript Language Surface v0.1 passed its complete release gate and is
released as a fixed Platform v0.1 Alpha interface.

```text
ReasonScript Source
  -> Surface AST
  -> Semantic AST
  -> Reason IR
  -> ExecutionPlan
```

## 2. Certification Results

| Scope | Result |
|---|---|
| Phase 1.1 AST Mapping | PASS, 16 tests |
| Phase 1.2 Expression and Pattern | PASS, 18 tests |
| Phase 1.3 Statement | PASS, 16 tests |
| Phase 1.6 Calculation | PASS, 16 tests |
| LS-1 Type | PASS, 13 tests |
| LS-2 Namespace | PASS, 13 tests |
| Core conformance | PASS, 8 tests |
| Release certification | PASS, 3 tests |
| Full Python regression | PASS, 217 tests, 1 skipped |
| HybridRuntime regression | PASS, 129 tests |
| Python bytecode compilation | PASS |
| JSON manifest validation | PASS |
| Git whitespace validation | PASS |

The skipped Python test is the existing conditional Go adapter check. The Go
toolchain is unavailable in this environment and no Language Surface release
criterion depends on that adapter.

## 3. Fixed Contracts

- immutable Surface AST;
- source order preservation;
- deterministic parsing and replay;
- module namespace and symbol registration;
- import, alias, visibility, and qualified name resolution;
- declaration and relation validation;
- expression and pattern precedence;
- statement placement and reference integrity;
- Calculation local scope and terminal Result;
- primitive and Reason State type validation;
- canonical `node_type` serialization and round trip;
- deterministic Semantic AST projection;
- `reason-ir/0.1` compatibility;
- `execution-plan/0.1` compatibility.

## 4. Release Artifacts

- `docs/ReasonScript_Language_Surface_v0.1_Release_Specification.md`
- `release/language-surface-v0.1/manifest.json`
- `release/language-surface-v0.1/run_release_validation.py`
- `release/language-surface-v0.1/reports/release_validation_results.json`
- `language_surface_release_tests/`
- this report

## 5. Compatibility

The release does not change the semantic AST, parser, compiler, Reason IR,
ExecutionPlan, or Calculation Semantics interface versions.

The repository-level `VERSION` remains the Platform release version
`0.1.0-alpha`; Language Surface uses its independent interface version
`reasonscript-language-surface/0.1`.

