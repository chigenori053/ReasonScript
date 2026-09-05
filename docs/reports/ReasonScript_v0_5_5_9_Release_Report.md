# ReasonScript v0.5.5.9 Release Report / リリース完了報告書

Status: RELEASE_CANDIDATE
Date: 2026-09-05

## Completion Summary

ReasonScript 0.5.5.9 integrates the merged numeric-semantics and
Tensor-lifecycle pull requests. The macOS arm64 package is prepared from the
clean release commit; the Windows x86_64 package is built separately from the
same commit on Windows.

## Implemented Features

- Deterministic numeric promotion and associated language/runtime regressions.
- Multiline parenthesized expressions and stable transition IDs.
- Deterministic cleanup of unreachable protected Tensor lifecycles.
- CI and playground pipeline robustness improvements.

## Validation Results

- Version metadata: 6/6 checks passed.
- Canonical CI foundation (`reason ci --skip-tests`): workspace, diagnostics,
  artifacts, golden corpus, agent protocol, and compatibility checks passed.
- Merged-PR regression suite: 28 passed.
- Local development-package provenance and install-side validation: passed.
- Installed `doctor`: 22 passed, 2 optional checks skipped, 0 failed.
- Installed `install-validate`: 36 passed, 0 failed.

## Compatibility Notes

Runtime compatibility remains `>=0.5.0,<0.6.0`. The macOS and Windows
packages must use the same clean release commit and remain native to their
respective target platforms.

## Remaining Work

- Run the full `reason ci --json` suite in an unrestricted terminal before
  publishing the release unit.
- Build and validate the Windows x86_64 archive from this same release commit.
