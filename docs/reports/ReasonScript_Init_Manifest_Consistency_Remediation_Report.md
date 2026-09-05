# ReasonScript Init / Manifest Consistency Remediation Report

Status: VALIDATED  
Date: 2026-09-05  
Issue: #38  
Related: #37

## Completion Summary

The init and Manifest documentation now reflects the implemented behavior.
`reason init` creates an explicit `[source] entry`, while projects without
that section retain recursive legacy `src/**/*.rsn` discovery. The same
source-selection rule is used by `check`, `build`, `run`, and project
validation. Missing explicit entries remain a `SourceEntryMissing` error.

## Validation Results

| Check | Result | Evidence |
|---|---|---|
| Multi-file legacy and explicit-entry regression tests | PASS (9 tests) | `tests/test_multifile_package_regression.py` |
| Related CLI/workspace tests | PASS (24 tests) | `tests/test_multifile_package_regression.py`, `tests/cli/test_workspace_foundation_phase7_1.py` |
| Source-tree `reason doctor --json` | PASS | `status=healthy`, `reason_version=0.5.5.9` |
| Installed-project smoke flow | PASS | `reason init`, `reason build`, and `reason run` all exited 0 |
| Canonical `reason ci --json` | PASS | Final candidate run after the worktree-root test fix |

The CI test previously failed because an IDE unit test required the checkout
directory name to be exactly `ReasonScript`. It now verifies the repository
contract (`reason.toml`, `frontend/`, and `toolchain/`) so isolated worktrees
are supported without weakening root discovery.

## Platform Evidence

| Target | Status in this run | Evidence |
|---|---|---|
| macOS arm64 | PASS | Local `doctor`, init/build/run, and canonical CI |
| macOS x86_64 | NOT EXECUTED HERE | No x86_64 runner in this session |
| Linux x86_64 | NOT EXECUTED HERE | No Linux runner in this session |
| Windows x86_64 | NOT EXECUTED HERE | No Windows runner in this session |

The repository declares these four supported targets. The three targets not
available in this session are explicitly recorded as **not locally
re-executed**, not as completed local validation. Their portable contract
coverage remains in the platform-independent CI and installation validation
suites.

## Compatibility Notes

Legacy manifests without `[source]` remain multi-file compatible. Explicit
`[source].entry` is validated but does not exclude sibling modules from the
package graph.

## Remaining Work

- Capture native install-package stdout/stderr and version output on each
  release target when those runners are available.
- Keep platform-specific CI results attached to release candidates.
