# ReasonScript Install Foundation v1.1 Update Installation

Released: 2026-07-14
ReasonScript Release Unit: 0.5.1
Status: Stage 1 `VALIDATED`

## Added

- Cross-platform local-package updates through `reason update`.
- Versioned staging and atomic active-pointer switching.
- Native Rust activation helper and macOS/Linux/Windows adapters.
- SHA-256 package and installed-file integrity verification.
- User-data preservation, automatic rollback, explicit rollback, and deterministic reports.
- v1.1 metadata schemas, package builder, validation fixtures, tests, and reports.

## Compatibility

Install Foundation v1.0 metadata is migrated once and its compatibility entry points remain readable. No existing project, Artifact, Runtime, Tensor, Phase 1R, Golden, or CI contract was intentionally removed.

## Validation

macOS arm64 lifecycle and canonical repository CI passed. Linux and Windows device certification remains pending.
