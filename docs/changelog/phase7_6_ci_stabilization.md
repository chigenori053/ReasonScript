# Phase 7.6 CI Stabilization

Implemented `reasonscript-ci/1.0`.

## Changes

- Added the Phase 7.6 CI Stabilization specification under `docs/specifications/`.
- Added `toolchain/ci.py` implementing the canonical CI pipeline: checkout, environment setup, workspace validation, diagnostics validation, artifact validation, golden tests, agent protocol validation, compatibility verification, and unit/integration tests.
- Added `reason ci` for direct pipeline execution, with `--json`, `--out`, and `--skip-tests` support.
- Added deterministic `ci_report.json` and `ci_summary.json` generation.
- Implemented CI validation rules `CI-001` through `CI-010`.
- Added `.github/workflows/ci.yml` running the canonical CI workflow on push and pull request.
- Updated `AGENTS.md` with the CI Stabilization workflow and validation rules.
