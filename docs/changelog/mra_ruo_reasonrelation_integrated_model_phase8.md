# MRA RUO / ReasonRelation Integrated Model — Phase 8

Date: 2026-08-11

- Added the explicit RUO-U1 to ReasonGraph integration boundary.
- RUO-U1 input is validated before projection and never mutated.
- Only resolved Unit-to-Unit U1 relations are promoted to canonical
  `ReasonRelation` records. Relations with non-Unit or unresolved endpoints
  remain in the compatibility extension for lossless reverse projection.
- RUO-F1, Native Runtime, ReasonScript operations, and MIRP transport remain
  out of scope.
