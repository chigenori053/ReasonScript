# MRA RUO / ReasonRelation — Native Runtime Handoff Phase 10 v0.1

Status: ACCEPTED
Specification ID: MRA-RUO-RR-NATIVE-HANDOFF-0.1
Date: 2026-08-12
Prerequisite: MRA-RUO-RR-F1-INT-0.1 and `reasonscript-reasonunit-native-runtime/1.0`

## Purpose

Phase 10 proves that a verified RUO-F1 Object has the same stable Unit identity
and logical digest at both the Native ReasonUnit Runtime boundary and the
ReasonGraph projection boundary.

## Normative behavior

- Native Runtime MUST load the RUO-F1 source before emitting its graph handoff.
- The handoff is read-only and contains only graph-relevant U1 metadata.
- Stable Unit IDs and the RUO-F1 logical Object digest MUST match the canonical
  Phase 9 ReasonGraph projection.
- The handoff MUST NOT create a native ReasonGraph type, mutate a native
  snapshot, alter RUO-F1 bytes, or claim graph execution support.

## Out of scope

Native ReasonGraph persistence/loading, native graph transactions or queries,
ReasonScript operations, MIRP transport, and graph execution.
