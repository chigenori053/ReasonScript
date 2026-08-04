# ReasonScript Install Foundation v1.1.1 Phase R1 Validation Report

## Completion Summary

Phase R1 is `VALIDATED` on macOS arm64. The current rollback defect is reproduced deterministically while active-pointer restoration and operational recovery are independently confirmed.

## Validation Results

| Validation | Result |
| --- | --- |
| Phase R1 focused tests | PASS (13) |
| Install/update regression | PASS (24) |
| Repository `./reason ci --json` | PASS (794 tests) |
| Workspace validation | PASS |
| Diagnostics validation | PASS |
| Artifact validation | PASS |
| Golden tests | PASS |
| Agent protocol validation | PASS |
| Compatibility verification | PASS |
| Rollback defect reproduction | PASS |
| Active pointer restoration | PASS |
| Restored launcher reports 0.5.0 | PASS |
| Legacy Phase 1R fixture mismatch | REPRODUCED |
| Current `INS-UPD-012` classification | REPRODUCED |
| Operational recovery contradiction | CONFIRMED |
| Deterministic rerun | PASS |

## Generated Artifacts

The canonical observation records the missing path using `<install-root>` and excludes timestamps, PIDs, and temporary prefixes. It matches the checked fixture expectation byte-for-byte after stable JSON serialization.

- `artifacts/install_foundation_v1_1_1/phase_r1/rollback_failure_reproduction_observation.json`
- `ci_report.json`
- `ci_summary.json`
- `agent_report.json`

## Compatibility Notes

No production behavior, schema, diagnostic contract, runtime semantic, artifact schema, or golden baseline changed. The test suite expects the known defect, so failure to reproduce it will fail the characterization tests and require an intentional Phase R2/R3 expectation update.

## Remaining Work

The rollback defect is not fixed in Phase R1. Validation-profile support, version-aware rollback validation, corrected diagnostic classification, and any future `failed_rolled_back` status remain later-phase work.
