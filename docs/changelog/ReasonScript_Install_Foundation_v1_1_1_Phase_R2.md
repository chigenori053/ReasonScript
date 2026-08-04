# ReasonScript Install Foundation v1.1.1 Phase R2 — Validation Profile Foundation

## Added

- Added immutable Validation Profile and capability models.
- Added release-local command, fixture, component, and schema capability detection.
- Added a legacy 0.5.0 fallback profile and a declared 0.5.1 Phase 1R profile.
- Added deterministic canonical serialization and machine-readable profile artifacts.
- Added path traversal, absolute path, invalid type, and symlink escape protection.

## Validation

- R2 focused tests: PASS (21)
- Phase R1 compatibility: PASS (13)
- Install/update regression: PASS (45)
- Schema validation: PASS
- Repository regression: PASS

## Compatibility

Production rollback and post-install validation behavior are unchanged. Install Update diagnostics, Current Installation metadata, Update Report schemas, Phase R1 canonical observation, runtime semantics, artifact semantics, golden behavior, and CI order remain unchanged.
