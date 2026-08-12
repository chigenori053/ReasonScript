# MRA RUO / ReasonRelation Integrated Model — Phase 4

Date: 2026-08-11

- Added a read-only Legacy RUO and RUO-U1 compatibility adapter that projects
  Unit-to-Unit relations into the ReasonGraph v0.1 reference model.
- Added exact snapshot-based reverse projection and independent `lossless` and
  `canonical_coverage` reports.
- Retained existing relations with non-Unit endpoints in compatibility metadata
  rather than discarding or misclassifying them as canonical ReasonGraph edges.
- Added RRI-015 through RRI-017 coverage for migration, reverse projection,
  and explicit loss/noncoverage reporting.
