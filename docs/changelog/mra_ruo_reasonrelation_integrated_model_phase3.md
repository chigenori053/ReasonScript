# MRA RUO / ReasonRelation Integrated Model — Phase 3

Date: 2026-08-11

- Added `GraphTransaction`, a copy-on-write transaction boundary for complete
  ReasonGraph proposals. Invalid or stale proposals preserve the original
  graph and report zero partial commits.
- Added deterministic RRI-018 through RRI-025 coverage for atomic updates,
  rollback, canonical serialization, independent-process byte identity,
  input-order independence, and Unit/Relation/Graph SHA-256 stability.
- Kept compatibility adapters, persistent Graph encoding, and MIRP projection
  out of scope for this phase.
