# MRA RUO / ReasonRelation Integrated Model — Phase 7

Date: 2026-08-11

- Added RGO-F1, a separate canonical JSON Lines persistence format for the
  validated ReasonGraph v0.1 reference model.
- Added atomic `.rgraph` writing, logical round-trip reading, content and
  record SHA-256 seals, canonical JSON enforcement, and tamper detection.
- Kept the existing RUO-F1 `.ruo` format unchanged; RUO-F1 integration remains
  a separate compatibility decision.
