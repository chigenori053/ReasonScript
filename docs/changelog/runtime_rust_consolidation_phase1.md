# Runtime Rust Consolidation Phase 1

- Added the installed native executable `reason-runtime-host` with profile
  `reasonscript-runtime-host/1.0`.
- Added versioned `reasonscript-runtime-request/1.0` and
  `reasonscript-runtime-result/1.0` envelopes and JSON Schemas.
- Preserved raw `reason-computation-ir/0.1` input compatibility during the
  migration.
- Updated the Python bridge to resolve an explicit host, an installed host,
  the distribution-local host, source-tree builds, or PATH.
- Added the host to source installation, update-package construction,
  provenance components, staged validation, and native smoke validation.
- Updated the Phase 0 manifest baseline to record that installed distributions
  now carry the Rust computation host.
