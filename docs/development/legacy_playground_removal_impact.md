# Legacy Playground Frontend — Removal Impact Analysis

Status: REVIEWED (Phase 4.5-A)

Scope: what breaks, today, if `playground/frontend` were physically deleted
without first completing Phase 4.5-B. This document exists so that the
deletion decision in a future phase can be made against a recorded baseline
rather than re-investigated from scratch.

Companion documents:
[ide_code_review_phase_4_5_a.md](ide_code_review_phase_4_5_a.md) (main
report), [ide_version_inventory.md](ide_version_inventory.md) (per-directory
detail).

## 1. What is explicitly NOT affected by this analysis

The following are out of scope for deletion and are confirmed unaffected by
any change proposed here:

- `playground/backend` (FastAPI backend — retained; its API surface is what
  both the legacy and official UIs call)
- `RuntimeReal`, `HybridRuntime` (retained Rust compatibility runtimes;
  the unreferenced `RuntimeComplex` placeholder was removed in Runtime Rust
  Consolidation Phase 9)
- `frontend` (the Python compiler/parser/LSP language frontend — confirmed
  in [ide_version_inventory.md](ide_version_inventory.md) to be unrelated to
  IDE UI work)

## 2. Scripts that break immediately on deletion

| File | Breaking reference | Effect if `playground/frontend` is deleted today |
|---|---|---|
| `scripts/dev.py` | `cmd_setup()`: `npm install` in `playground/frontend` | `setup` fails |
| `scripts/dev.py` | `cmd_frontend()`: `npm run dev` in `playground/frontend` | `frontend` command fails |
| `scripts/dev.py` | `cmd_build()`: `npm run build` in `playground/frontend` | `build` command fails |
| `scripts/dev.py` | `cmd_test("smoke")`: `npm run build` in `playground/frontend` | `test smoke` fails |
| `scripts/dev.py` | `cmd_test("frontend")`: `npm run build` in `playground/frontend` | `test frontend` fails |
| `playground/start.sh` | `cd "$PLAYGROUND/frontend" && npm run dev` | `dev.py playground` (and the script directly) fails |
| `scripts/check_environment.py` | `REQUIRED_PATHS` includes `"playground/frontend"` | `check` reports `[FAIL]` / missing path |

`scripts/test_platform.py` is **not** in this table: its `NPM_PROJECTS` loop
checks `package_json.exists()` before acting, so it degrades gracefully if
the directory is removed (it simply skips the project). This script does not
need to change before deletion, though it stops validating anything about
the legacy UI once it is gone (which is the intended end state).

## 3. Tests that break immediately on deletion

None. `tests/ide` (22 files), `tests/playground` (7 files),
`tests/compatibility` (5 files), and `playground_integration_tests`
(1 file) all exercise `playground/backend`'s API surface or standalone
Python contracts — none of them build or import anything from
`playground/frontend`. This was confirmed by reading each test directory's
file list and cross-checking against `PYTEST_GROUPS` in
`scripts/test_platform.py`.

The only test-shaped breakage is indirect: `scripts/dev.py test smoke` and
`test frontend` invoke `npm run build` in `playground/frontend` as part of
their command bodies (see Section 2), so "the smoke test" as currently
defined would fail — not because a pytest suite references the directory,
but because `scripts/dev.py` hardcodes the path in a shell step.

## 4. Documentation that becomes stale or incorrect on deletion

| Doc | Current statement | Problem after deletion |
|---|---|---|
| `docs/development/editor_state_contract.md` | "Implemented client-side in `playground/frontend/src/App.jsx`" | Describes a file that no longer exists as the canonical implementation |
| `docs/development/commands.md` | `frontend`/`build`/`test frontend` sections all describe `playground/frontend` paths and `npm run dev -- --port 5173` | All command descriptions become inaccurate |
| `docs/development/test_matrix.md` | Frontend Test Scope: `playground/frontend/ → npm run build` | Describes a nonexistent path |
| `docs/specs/reasonscript_language_layer_v0_6_d.md` | `cd playground/frontend && npm run build` | Broken instruction |
| `docs/development/environment.md` | Node/npm requirements framed around "Playground frontend" | Still technically true (official IDE UI also needs Node/npm) but should be reworded to be UI-agnostic |

## 5. Features that would be silently dropped

16 of 32 tracked features exist only in `playground/frontend` today (see the
Feature Parity Matrix in
[ide_code_review_phase_4_5_a.md](ide_code_review_phase_4_5_a.md#feature-parity-matrix)
for the full list and per-row classification). In summary:

- **12 features requiring migration** before deletion is acceptable: Audit,
  Runtime IO output, Input state, Calculation panel, Cycle diagnostics,
  Runtime trace, Strict diagnostics, Ownership analysis, Type coverage,
  Exhaustiveness, Determinism, Complexity, Export, Import, Diff, Language
  audit matrix. (Note: list is 15 after de-duplicating Audit/Language audit
  matrix as related; see main report for exact per-row status.)
- **4 features needing an explicit product decision** (likely CI/QA/dev
  tooling, not end-user IDE features, but this CodeReview does not have
  authority to decide unilaterally): Run all, Baseline, Regression runner,
  Sample selector.

Deleting `playground/frontend` before these are migrated or explicitly
deprecated would remove this functionality from the repository with no
record of the decision to drop it.

## 6. Deletion Gate Checklist (authoritative — mirrors Section 10 of the governing spec)

- [ ] `scripts/dev.py` has no `playground/frontend` launch reference
- [ ] `scripts/test_platform.py` has no `playground/frontend` build reference
      (or its presence is an explicit, documented legacy-compat step)
- [ ] Documentation no longer treats `playground/frontend` as the official IDE
- [ ] Official IDE UI (`apps/reasonscript-ide/ui`) build is included in
      `test smoke`
- [ ] All 16 legacy-only features are migrated, explicitly deprecated, or
      moved to backend-only with product sign-off
- [ ] `grep -R "playground/frontend" -n scripts docs tests apps playground package.json`
      returns no unaccounted-for references
- [ ] `python3 scripts/dev.py test smoke|backend|ide` and the rewired
      `test frontend`/`test ide-ui` all pass

**Status as of this review: 0 of 7 conditions met.** Physical deletion must
not proceed until Phase 4.5-B closes these items and this checklist is
re-run and re-recorded as VALIDATED.

## 7. Recommendation

Do not delete `playground/frontend` in this phase. Treat this document as
the standing record of "why not yet" for any future attempt to remove it
before Phase 4.5-B is complete.
