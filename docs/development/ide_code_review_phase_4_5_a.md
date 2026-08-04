# ReasonScript IDE Phase 4.5-A CodeReview Report

## Status

REVIEWED

Deletion Gate: NOT MET
Next Phase: Phase 4.5-B — Official IDE Command Wiring

## Summary

This CodeReview investigated the three `frontend`/`ui` directories in the
repository (`apps/reasonscript-ide/ui`, `playground/frontend`, `frontend`),
classified their roles, mapped their command / test / documentation / API
dependencies, and identified the feature gap between the legacy Playground
UI and the official IDE UI.

Findings:

- `frontend` is a pure Python compiler/parser/AST/LSP/schema package. It has
  no relation to any UI and must not be considered for deletion under this
  initiative.
- `apps/reasonscript-ide/ui` is the candidate official IDE UI (React + Vite +
  TypeScript + Tauri adapters), but it is **not wired into `scripts/dev.py`**,
  the repository's official developer entry point. It is only referenced by
  the newer `scripts/test_platform.py`.
- `playground/frontend` is the legacy Playground UI. It is still the only
  frontend that `scripts/dev.py` launches, builds, or tests, and it exposes
  16 features / API endpoints that have no counterpart in the official IDE
  UI.
- Physical deletion of `playground/frontend` is **not currently safe**: doing
  so today would break `scripts/dev.py playground|frontend|build|test smoke|test frontend`
  and would silently drop 16 unmigrated features.

See [ide_version_inventory.md](ide_version_inventory.md) for the full
per-directory inventory and [legacy_playground_removal_impact.md](legacy_playground_removal_impact.md)
for the detailed deletion-impact analysis.

## Directory Inventory

| Path | Classification | Role | Delete Candidate | Notes |
|---|---|---|---|---|
| `apps/reasonscript-ide/ui` | OFFICIAL_IDE_UI | React/Vite/TS IDE UI with `PlatformAdapter` (browser + Tauri desktop) | No | Not wired into `scripts/dev.py`; only known to `scripts/test_platform.py` |
| `playground/frontend` | LEGACY_IDE_UI | React/Vite/JSX Playground UI, original prototype IDE | Yes, after Phase 4.5-B gate is met | Sole target of `scripts/dev.py`'s frontend commands today |
| `frontend` | LANGUAGE_FRONTEND | Python compiler/parser/AST/LSP/DTO/schema package | No — out of scope entirely | Not a UI; no `package.json`; referenced by `frontend.lsp`, `frontend.compiler`, conformance suites, VSCode extension |

## Command Dependency Matrix

| Command | Current Target | Expected Target | Action |
|---|---|---|---|
| `setup` | `npm install` in `playground/frontend` only | should also `npm install` in `apps/reasonscript-ide/ui` | update |
| `check` | delegates to `check_environment.py`, which checks `playground/frontend` path only | should also check `apps/reasonscript-ide/ui` | update |
| `playground` | `playground/start.sh` → `playground/frontend` (5173) + `playground/backend` (8000) | unchanged (legacy dev workflow, kept until deletion gate met) | keep, mark legacy |
| `frontend` | `playground/frontend` npm dev server | ambiguous name — currently means legacy UI only | rename to `playground-frontend` or deprecate |
| `ide` | looks for `ide/desktop` (Tauri project that does not exist in this repo); prints "not available" | should launch `apps/reasonscript-ide/ui` (`npm run dev` / `npm run tauri dev`) | **broken — needs new implementation** |
| `backend` | `playground/backend` via uvicorn | unchanged | keep |
| `build` | `npm run build` in `playground/frontend` only | should also build `apps/reasonscript-ide/ui` | **missing official IDE build — add step** |
| `test smoke` | `tests/compatibility` + `playground_integration_tests` + `playground/frontend` build | should include `apps/reasonscript-ide/ui` build | **missing official IDE build — add step** |
| `test frontend` | `npm run build` in `playground/frontend` only | naming implies "the frontend," but only covers legacy UI | rename to `test playground-frontend`; add `test ide-ui` for the official UI |
| `test backend` | `tests/compatibility` + `playground_integration_tests` + `tests/playground` | unchanged | keep |
| `test rust` | `RuntimeReal`, `HybridRuntime` cargo test | unchanged | keep |
| `test ide` | `ide_phase1_tests` + `tests/ide` (Python contract tests; no UI build involved) | unchanged, but does not validate `apps/reasonscript-ide/ui`'s actual build | keep, but does not substitute for a UI build/lint step |
| `test all` | runs `backend`, `frontend`, `rust`, `ide` in sequence | should also run the official IDE UI build | update once new command exists |

Expected end state (per spec ยง5.4), not yet implemented:

```
python3 scripts/dev.py ide        -> Official IDE workflow (apps/reasonscript-ide/ui)
python3 scripts/dev.py ide-ui     -> apps/reasonscript-ide/ui (explicit alias)
python3 scripts/dev.py backend    -> playground/backend
python3 scripts/dev.py frontend   -> deprecated or removed (legacy alias)
python3 scripts/dev.py playground -> deprecated or removed (legacy alias)
python3 scripts/dev.py test frontend -> apps/reasonscript-ide/ui build
python3 scripts/dev.py test smoke    -> official IDE UI build included
```

## Test Dependency Matrix

| Test Command | Current Target | Expected Target | Action |
|---|---|---|---|
| `tests/ide` (22 files, Python) | Adapter/workspace/command-registry contracts — no UI build dependency | unchanged | none — already deletion-safe |
| `tests/playground` (7 files, Python) | `/api/analyze`, artifact, diagnostics, projection contract tests — backend only | unchanged | none — already deletion-safe |
| `tests/compatibility` | Language surface / compiler compatibility — no UI dependency | unchanged | none |
| `playground_integration_tests` | `/api/*` integration via backend — no UI build dependency | unchanged | none |
| `scripts/dev.py test smoke` | Hardcodes `npm run build` in `playground/frontend` | should not hard-fail if `playground/frontend` is removed | **breaks on deletion — must update first** |
| `scripts/dev.py test frontend` / `build` | Hardcodes `playground/frontend` | same | **breaks on deletion — must update first** |
| `scripts/test_platform.py build/lint` | Iterates `NPM_PROJECTS = [playground/frontend, apps/reasonscript-ide/ui]`, skips missing dirs | tolerant of removal already | none — already deletion-safe |

Conclusion: the actual pytest suites (`tests/ide`, `tests/playground`, `tests/compatibility`,
`playground_integration_tests`) never assumed the legacy UI exists — they test
backend/API contracts only. The only hard dependency on `playground/frontend`
existing is in `scripts/dev.py`'s shell command wiring, which is exactly what
Phase 4.5-B must fix before deletion is possible.

## API Usage Matrix

| API | apps/reasonscript-ide/ui | playground/frontend | Keep Backend API |
|---|---:|---:|---:|
| `/api/analyze` | ✓ | ✓ | Yes |
| `/api/core` | ✓ | — | Yes |
| `/api/workspace/list` | ✓ | ✓ | Yes |
| `/api/workspace/read` | ✓ | ✓ | Yes |
| `/api/workspace/save` | ✓ | ✓ | Yes |
| `/api/validate` | — | ✓ | Yes (until migration decision made) |
| `/api/run-all` | — | ✓ | Yes (until migration decision made) |
| `/api/pipeline` | — | ✓ | Yes (client-side `PipelineOverviewView` already exists in official IDE, derived from `/api/analyze`; standalone endpoint usage not yet ported) |
| `/api/export` | — | ✓ | Yes (until migration decision made) |
| `/api/import` | — | ✓ | Yes (until migration decision made) |
| `/api/diff` | — | ✓ | Yes (until migration decision made) |
| `/api/baseline` | — | ✓ | Yes (until migration decision made) |
| `/api/language-audit` | — | ✓ | Yes (until migration decision made) |
| `/api/language-audit/export` | — | ✓ | Yes (until migration decision made) |
| `/api/examples` | — | ✓ | Yes (until migration decision made) |

Architectural note: `apps/reasonscript-ide/ui`'s `bridge.ts` derives nearly
all view state (`validation`, `analyzer`, `runtime_operations`, `simulation`,
`knowledge`, `diagnostics`) from a single `/api/analyze` response, whereas
`playground/frontend` calls many dedicated endpoints per feature. This means
several "not ported" rows above (`/api/validate`, `/api/run-all`, `/api/export`,
`/api/import`, `/api/diff`, `/api/baseline`, `/api/language-audit*`,
`/api/examples`) require **new client integration work**, not just moving
existing UI code, since the official IDE's data-fetching pattern differs from
the legacy one.

## Feature Parity Matrix

| Feature | Official IDE | Legacy Playground | Action |
|---|---:|---:|---|
| Analyze | ✓ | ✓ | ALREADY_SUPPORTED |
| Run | ✓ (via `runtime_operations` in analyze response) | ✓ | ALREADY_SUPPORTED |
| Validate | ✓ (`ValidationView`, derived from analyze response) | ✓ (dedicated `/api/validate` call) | ALREADY_SUPPORTED (behavior differs — see API note above) |
| Audit | — | ✓ (`LanguageAuditPanel`) | MIGRATE_REQUIRED |
| Pipeline view | ✓ (`PipelineOverviewView`) | ✓ (`PipelineOverviewPanel`) | ALREADY_SUPPORTED |
| AST view | ✓ (`SourceModelView`) | ✓ | ALREADY_SUPPORTED |
| Semantic AST view | ✓ (`JsonArtifactView` semantic_ast.json) | ✓ | ALREADY_SUPPORTED |
| Reason IR view | ✓ (`ReasonIRView`) | ✓ | ALREADY_SUPPORTED |
| ExecutionPlan view | ✓ (`ExecutionPlanView` / `ExecutionPlanFlowView`) | ✓ (`ExecutionPlanPanel`) | ALREADY_SUPPORTED |
| Simulation view | ✓ (`SimulationTraceView`) | ✓ (`SimulationPanel`) | ALREADY_SUPPORTED |
| Knowledge view | ✓ (`KnowledgeEvidenceView`) | ✓ (`KnowledgePanel`) | ALREADY_SUPPORTED |
| Diagnostics view | ✓ (`DiagnosticsView`) | ✓ (`DiagnosticsPanel`) | ALREADY_SUPPORTED |
| Runtime IO output | not confirmed (no raw console/stdout view found) | ✓ (`Console`, `OutputPanel`) | MIGRATE_REQUIRED (needs confirmation) |
| Dependency graph | ✓ (`DependencyGraphView`) | ✓ (`DependencyGraphPanel`) | ALREADY_SUPPORTED |
| Runtime operations | ✓ (`RuntimeOperationsView`) | ✓ (`RuntimeOperationsPanel`) | ALREADY_SUPPORTED |
| Input state | — | ✓ (`InputStatePanel`) | MIGRATE_REQUIRED |
| Calculation panel | — | ✓ (`CalculationPanel`) | MIGRATE_REQUIRED |
| Cycle diagnostics | — | ✓ (`CyclePanel`) | MIGRATE_REQUIRED |
| Runtime trace | not confirmed distinct from Simulation | ✓ (`RuntimeTracePanel`) | MIGRATE_REQUIRED (needs product decision: may already be covered by `SimulationTraceView`) |
| Strict diagnostics | — | ✓ (`StrictDiagnosticsPanel`) | MIGRATE_REQUIRED |
| Ownership analysis | — | ✓ (`OwnershipPanel`) | MIGRATE_REQUIRED |
| Type coverage | — | ✓ (`TypeCoveragePanel`) | MIGRATE_REQUIRED |
| Exhaustiveness | — | ✓ (`ExhaustivenessPanel`) | MIGRATE_REQUIRED |
| Determinism | — | ✓ (`DeterminismPanel`) | MIGRATE_REQUIRED |
| Complexity | — | ✓ (`ComplexityPanel`) | MIGRATE_REQUIRED |
| Export | — | ✓ (`ExportPanel`, `/api/export`) | MIGRATE_REQUIRED |
| Import | — | ✓ (`/api/import`) | MIGRATE_REQUIRED |
| Diff | — | ✓ (`DiffPanel`, `/api/diff`) | MIGRATE_REQUIRED |
| Run all | — | ✓ (`RegressionRunner`, `/api/run-all`) | NEEDS PRODUCT DECISION — likely CI/QA tooling rather than end-user IDE feature; candidate for BACKEND_ONLY / DEPRECATE_ALLOWED |
| Baseline | — | ✓ (`BaselinePanel`, `/api/baseline`) | NEEDS PRODUCT DECISION — same rationale as Run all |
| Regression runner | — | ✓ (`RegressionRunner`) | NEEDS PRODUCT DECISION — same rationale as Run all |
| Language audit matrix | — | ✓ (`LanguageAuditPanel`, `/api/language-audit`) | MIGRATE_REQUIRED |
| Sample selector | — | ✓ (`/api/examples`) | NEEDS PRODUCT DECISION — likely dev convenience, not core IDE feature |

16 of 32 tracked features have no official-IDE counterpart today. Of those,
4 (Run all, Baseline, Regression runner, Sample selector) look like
CI/QA/dev-convenience tooling rather than end-user IDE features and should be
explicitly decided (migrate vs. deprecate vs. keep backend-only) by product
owners before the deletion gate can close — this CodeReview does not have
authority to make that call unilaterally.

## Documentation Impact

- [editor_state_contract.md](editor_state_contract.md) states client-side
  state is "Implemented client-side in `playground/frontend/src/App.jsx`."
  This treats the legacy UI as canonical and must be updated once
  `apps/reasonscript-ide/ui/src/state/{projectStore,workspaceStore}.ts`
  becomes the authoritative implementation.
- [commands.md](commands.md) and [test_matrix.md](test_matrix.md) describe
  `frontend`/`build`/`test frontend` exclusively in terms of
  `playground/frontend`; no mention of `apps/reasonscript-ide/ui` exists in
  either doc.
- `docs/specs/reasonscript_language_layer_v0_6_d.md` instructs
  `cd playground/frontend && npm run build` as the canonical frontend build
  step.
- [platform_adapter_core.md](platform_adapter_core.md) and
  [cross_platform_path_policy.md](cross_platform_path_policy.md) already
  reference `apps/reasonscript-ide/ui` structurally (file paths for adapters)
  but do not declare it "the official IDE UI" anywhere.
- No document currently states a removal plan or timeline for
  `playground/frontend`.

## Deletion Impact

See [legacy_playground_removal_impact.md](legacy_playground_removal_impact.md)
for the full breakdown. Summary: deleting `playground/frontend` today would
immediately break `scripts/dev.py playground|frontend|build|test smoke|test frontend`,
and would silently drop 16 features with no migration path. `playground/backend`,
`RuntimeReal`, `HybridRuntime`, `RuntimeComplex`, and `frontend` (the Python
language frontend) are unaffected and out of scope.

## Required Migrations

Before `playground/frontend` can be physically deleted:

1. Wire `apps/reasonscript-ide/ui` into `scripts/dev.py` (new/renamed
   commands per the Command Dependency Matrix above).
2. Add `apps/reasonscript-ide/ui` build to `scripts/dev.py build` and
   `test smoke`.
3. Resolve the 16-feature gap in the Feature Parity Matrix — for each row,
   decide MIGRATE_REQUIRED, DEPRECATE_ALLOWED, or BACKEND_ONLY, and execute
   that decision.
4. Update `docs/development/editor_state_contract.md`, `commands.md`,
   `test_matrix.md`, and `docs/specs/reasonscript_language_layer_v0_6_d.md`
   to reference `apps/reasonscript-ide/ui` as the official IDE UI.

## Safe Deletion Conditions

Per Section 10 of the governing spec, all of the following must be true
before `playground/frontend` is physically removed:

- [ ] `scripts/dev.py` has no `playground/frontend` launch reference
- [ ] `scripts/test_platform.py` has no `playground/frontend` build reference
      (or its presence is an explicit, documented legacy-compat step)
- [ ] Documentation no longer treats `playground/frontend` as the official IDE
- [ ] Official IDE UI build is included in `test smoke`
- [ ] Legacy-only features are migrated or explicitly deprecated (product
      decision recorded)
- [ ] `grep -R "playground/frontend"` returns no unaccounted-for references
- [ ] `test smoke` / `test backend` / `test ide` / `test frontend` all pass
      against the new wiring

**Current state: none of the above are met.** This CodeReview establishes the
baseline; Phase 4.5-B is the implementation phase that closes these items.

## Final Recommendation

Do not delete `playground/frontend` yet. Proceed to Phase 4.5-B
("Official IDE Command Wiring") to:

1. Wire `apps/reasonscript-ide/ui` into `scripts/dev.py` and `test smoke`/`build`.
2. Get an explicit product decision on the 4 CI/QA-flavored features (Run all,
   Baseline, Regression runner, Sample selector).
3. Migrate the remaining 12 MIGRATE_REQUIRED features (or explicitly
   deprecate them with sign-off) before scheduling Phase 4.5-C (physical
   deletion).

`frontend` (the Python language frontend) and `playground/backend` require
no action under this initiative and should not be referenced again in future
deletion-planning phases except as explicitly-excluded, unaffected systems.
