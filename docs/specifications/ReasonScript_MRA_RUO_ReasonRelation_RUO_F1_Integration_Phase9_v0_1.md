# MRA RUO / ReasonRelation — RUO-F1 Integration Phase 9 v0.1

Status: ACCEPTED
Specification ID: MRA-RUO-RR-F1-INT-0.1
Date: 2026-08-12
Prerequisite: MRA-RUO-RR-U1-INT-0.1 and `reasonscript-reasonunit-object-file/1.0`

## Purpose

Phase 9 provides a read-only, verified boundary from a complete canonical
RUO-F1 `.ruo` file to a ReasonGraph v0.1 value or RGO-F1 `.rgraph` file.

## Normative behavior

- A source MUST pass strict RUO-F1 physical, integrity, and semantic validation
  before its U1 logical Object is read.
- Projection MUST NOT alter source bytes.
- The Phase 8 RUO-U1 promotion and retention policy applies unchanged.
- The projection report MUST retain source object/revision and content/logical
  digests, but not an environment-dependent source path; it records only the
  source filename.
- An optional RGO-F1 output MUST be produced through the canonical atomic
  writer.

## Out of scope

Native Runtime graph types, native `.rgraph` loading, ReasonScript syntax and
operations, MIRP transport, automatic migration writes, and graph execution.
