# ReasonScript CI Test Consistency / Environment Parity v0.1

Implementation notes and verification record. Section numbers (§) refer to the specification.

## Contract

```text
Local ──┐
        ├─▶ scripts/test_platform.py test ◀── ./reason ci (tests phase)
CI ─────┘             GitHub Actions "Test" job
```

The same repository, the same declared dependencies, and the same command give the same result. The result depends on
repository *content*, declared dependencies, and an explicitly prepared CI environment, never on the checkout path or on
what a developer machine happens to have installed (§4).

| Situation | Local | `CI=true` |
| --- | --- | --- |
| checkout directory is named anything (worktree, fork, renamed clone) | PASS | PASS |
| `vscode-extension/node_modules` missing | the two extension tests **SKIP** with the reason; plan PASS | **FAIL** before any test (preflight), and the tests themselves fail with the fix |
| `node_modules` present (`npm ci` done) | tests run and PASS | tests run and PASS |

## What changed

* **Repository root (§7–§13).** No test compares a directory name. The Rust test is
  `repo_root_is_the_reasonscript_repository` (`apps/reasonscript-ide/src-tauri/src/compiler_bridge.rs`): `frontend/`,
  `toolchain/`, and `ReasonRuntime/` must exist under the root. Python has the same rule in
  `scripts/test_environment.py` (`is_reasonscript_repo_root`, `find_repo_root`); it uses markers only, so it works in
  source archives without `.git`.
* **One environment module (§79–§83).** `scripts/test_environment.py` owns `is_ci()` (`CI` unset, empty, `0`, `false`,
  `no`, `off` is not CI), `has_vscode_dependencies()`, `vscode_dependency_action()` (`run` / `skip` / `fail` plus the message),
  and `require_vscode_dependencies()`. The two extension tests call it; a test in the suite scans the repository so no test
  reimplements `environ.get("CI")` or `node_modules` checks.
* **Messages (§87–§89).** Local: `SKIPPED: vscode-extension/node_modules not found. Run `npm ci` in vscode-extension to
  enable this local test.` CI: `FAILED: CI requires vscode-extension/node_modules. The workflow must run `npm ci` before the
  Test job.`
* **Dependency preflight (§19–§23).** `scripts/test_platform.py preflight`, and automatically before `test`,
  `release-check`, and `integration`:

  ```text
  Test environment preflight (local mode)
    Python       READY
    Rust         READY
    Node         READY
    npm          READY
    VSCode deps  MISSING (local optional: VS Code extension tests are skipped; run `npm ci --prefix vscode-extension`)
    Runtime host BUILT BY THE PLAN (cargo build --bin reason-runtime-host)
  ```

  Under CI a missing requirement prints `MISSING (required in CI)` and exits 1 before any test runs.
* **Skip classification and the CI skip guard (§29–§31, §70–§78).** `scripts/test_report.py` is a pytest plugin the plan loads
  (`PYTEST_ADDOPTS=-p scripts.test_report`; the pytest command line is unchanged). It prints a summary
  `PASS / FAIL / SKIP_OPTIONAL / SKIP_PLATFORM / SKIP_UNKNOWN`, one line per skip with its reason, and whether each CI-required
  group executed (`vscode-extension-typescript: executed`). It never changes which tests run. Under CI the plan fails when a
  CI-required group did not execute (full plan only, not for filtered runs), or when a test skipped on a missing declared
  dependency. An unclassified skip is a **warning** by default and an error with `REASONSCRIPT_STRICT_SKIPS=1`: the current
  baseline has optional skips (Matplotlib, an external dataset) whose CI behaviour cannot all be observed, and a fixed skip count
  is brittle (§73). The summary avoids the phrase "N passed", so `./reason ci` does not count it twice.
* **Workflow contract (§90).** `tests/ci/test_environment_parity.py` checks that `test.yml`, `ci.yml`, and `release.yml` run
  `npm ci` in `vscode-extension` (lockfile only, never `npm install`) before the test plan, and that `test.yml` / `ci.yml` define
  no test list of their own. The existing `tests/ci/test_ci_stabilization.py` already pins the entrypoints.

### Test classification (§24–§28)

| Class | Meaning | Members |
| --- | --- | --- |
| CORE | no environment dependence, always runs | ReasonRuntime Rust tests, compiler / runtime / Python core suites |
| OPTIONAL_LOCAL | skips locally without the dependency (with a reason) | the extension tests without `node_modules`; Matplotlib / dataset tests |
| CI_REQUIRED | must execute in the full CI plan | `vscode-extension-typescript`, `vscode-extension-dependencies` (`CI_REQUIRED_TESTS`) |
| ENVIRONMENT_SPECIFIC | explicit platform condition | symlink tests |

### Reproducing CI locally (§46–§48)

```bash
npm ci --prefix vscode-extension
CI=1 python3 scripts/test_platform.py test
CI=1 ./reason ci
```

## Verification

| Case | Result |
| --- | --- |
| A renamed clone / B worktree (§62, §63) | `test_a_renamed_clone…`, `test_b_git_worktree…` (a real `git worktree` named `not-ReasonScript-worktree`); the Rust root test also ran green from a second worktree named `renamed-clone-xyz` |
| C local, no `node_modules` (§64) | plan exit 0, 2 extension tests `SKIP_OPTIONAL` with the reason, other suites PASS |
| D local, `node_modules` (§65) | `npm ci` done: both groups `executed`, exit 0 |
| E `CI=1`, no `node_modules` (§66) | preflight fails before any test (exit 1); run directly, both tests fail with the CI message |
| F `CI=1`, `npm ci` done (§67) | both groups `executed`, exit 0 |
| G `scripts/test_platform.py test` (§68) | exit 0 in C, D, F |
| H `./reason ci` (§69) | tests phase PASS without `CI` and without `node_modules`; FAIL with `CI=1` and no `node_modules`; PASS with `CI=1` and dependencies; always the same as the plan |
| Tauri / Python / ruff (§98) | 20 passed / 2593 passed, 3 skipped (Matplotlib ×2, external dataset) / clean |
| Regression | the pre-existing runtime, compiler, install, and CI suites pass unchanged |

Not verified here: the GitHub Actions runs themselves (Gates G, H) — the branch has not been pushed, and the workflows only
trigger on pull requests and pushes to `main`.

## Scope and follow-ups

* No formatting change. `cargo fmt --check` flags files that were already unformatted
  (`reason-object-core/src/lib.rs`, `apps/reasonscript-ide/src-tauri/src/commands.rs`); the `Lint` workflow does not run it, so it is
  separate from test parity (§51–§55) and belongs to a "Repository Formatting Normalization" change.
* `manifest-consistency.yml` (Init) keeps its own small pytest list on purpose; it is an init/manifest contract on three OSes, not
  the test plan.
* The preflight does not install anything (§50). `REASONSCRIPT_CI` (§44) is not added; `CI` alone is used (§45).
* Merge order (§113–§115): this branch is based on `main` and independent of the causal-relevance branch; merge it first, then
  rebase or merge `main` into the feature branch.
