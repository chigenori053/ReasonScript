# ReasonScript Install Foundation v1.1.1 Phase R1 — Rollback Failure Reproduction

## Added

- Added a deterministic legacy 0.5.0 installation fixture without Phase 1R validation resources.
- Added a deterministic 0.5.1 update package fixture with forced post-install validation failure.
- Added rollback lifecycle characterization tests and a canonical observation artifact.
- Added independent observations for update failure, pointer restoration, launcher recovery, rollback validation failure, and operational recovery.

## Validation

- 0.5.0 to failed 0.5.1 update reproduction: PASS
- Active pointer restoration to 0.5.0: PASS
- Restored launcher execution: PASS
- Missing legacy Phase 1R fixture condition: REPRODUCED
- Current `INS-UPD-012` classification: REPRODUCED
- Restored 0.5.0 operational health: CONFIRMED
- Deterministic rerun: PASS
- Repository regression: PASS (794 tests)

## Compatibility

No production rollback behavior, diagnostic contract, metadata schema, update report schema, runtime semantics, artifact semantics, golden behavior, or CI execution order changed.
