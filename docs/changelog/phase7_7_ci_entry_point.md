# Phase 7.7 Canonical CI Entry Point

Implemented `reasonscript-ci-entry/1.0`.

## Changes

- Added the Canonical CI Entry Point specification under `docs/specifications/`.
- Added `toolchain/ci_entry.py` validating the entry point contract: pipeline presence, fixed execution order, required validation contracts, report generation, and fail-fast termination semantics.
- Added `reason ci-entry` for direct entry-point contract validation, with `--json` support.
- Implemented entry point validation rules `CE-001` through `CE-005`.
- Documented `reason ci` as the canonical validation entry point in `AGENTS.md`, including the Coding Agent Policy and CI Policy sections.
- Added Compatibility Verification to the documented canonical workflow order in `AGENTS.md` to match the implemented pipeline.
- Consolidated `.github/workflows/test.yml` to invoke `reason ci` instead of duplicating agent protocol validation.
