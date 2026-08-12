# MRA RUO / ReasonRelation Integrated Model — Phase 9

Date: 2026-08-12

- Added a strict, read-only RUO-F1 `.ruo` to ReasonGraph integration boundary.
- The adapter verifies RUO-F1 before reading, retains provenance digests, and
  can atomically publish a canonical RGO-F1 `.rgraph` projection.
- Native Runtime graph types, ReasonScript operations, and MIRP transport
  remain separate future work.
