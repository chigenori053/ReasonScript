# ReasonScript MRA: RUO / ReasonRelation Integrated Model v0.1

Status: ACCEPTED — Phase 1 specification baseline
Specification ID: MRA-RUO-RR-IM-0.1
Date: 2026-08-11
Compatibility target: Existing ReasonUnit Object architecture

## 1. Purpose and Phase 1 scope

This specification introduces a graph-native Reason Object Model for MRA.
`ReasonUnit` is a node, `ReasonRelation` is a first-class semantic edge, and
`ReasonGraph` is the canonical representation of their connectivity.

Phase 1 fixes the data-model contract and validation matrix only. It does not
modify the ReasonScript grammar, parser, compiler, RuntimeReal execution graph,
Native ReasonUnit Runtime, RUO-F1 file format, or MIRP transport. A later
phase may integrate a validated reference model with those systems.

The Phase 1 implementation target is a standalone, JSON-compatible reference
model. Existing RUO behavior remains authoritative and unchanged until that
model passes the complete RRI matrix and its RUO regression suite.

## 2. Normative model

```text
ReasonObject
├── ReasonUnit
└── ReasonRelation

ReasonGraph = (units, relations)
```

Every canonical Reason Object has a stable ID, kind, lifecycle, provenance,
and metadata. In v0.1 only `unit` and `relation` are canonical Reason Object
kinds. Evidence remains an independently identified registry record referenced
by Objects; it is not a third Reason Object kind in v0.1.

Canonical logical shapes are:

```text
ReasonUnit {
  unit_id, unit_type, state, payload, evidence_refs,
  lifecycle, provenance, metadata
}

ReasonEntityRef { entity_kind: unit | relation, entity_id }

ReasonRelation {
  relation_id, source: ReasonEntityRef, target: ReasonEntityRef,
  relation_type, direction, strength?, evidence_refs, temporal_scope?,
  validation_state, lifecycle, provenance, metadata
}

ReasonGraph {
  graph_id, units[], relations[], root_refs[], lifecycle, provenance, metadata
}
```

`incoming_relation_refs` and `outgoing_relation_refs` are derived query
results, never persisted in a canonical Unit. The `relations[]` registry in a
ReasonGraph is the single source of truth for connectivity.

## 3. Identity, canonicalization, and hashes

The initial implementation uses the existing stable namespaces:

- Unit IDs: `ruo:unit:<token>`
- Relation IDs: `ruo:relation:<token>`
- Graph IDs: `ruo:graph:<token>`

`RR-000001` may be rendered as a presentation alias but is not a canonical
identity. A generated identity MUST derive only from versioned generation
inputs, such as an explicit legacy ID or `(migration-profile, source-digest,
stable-locator, entity-kind)`. Time, host, worker, file path, input order,
array position, and runtime timestamps MUST NOT contribute to identity.

Canonical serialization uses UTF-8, NFC Unicode, sorted object keys, stable
identity ordering for set-like registries, normalized finite numbers, and LF
line endings. SHA-256 is the v0.1 hash algorithm. `UnitHash`, `RelationHash`,
and `GraphHash` are calculated independently from their canonical logical
representations. A GraphHash includes canonical Units and Relations but no
environment-dependent value.

## 4. Relation semantics

Core relation types are `causes`, `supports`, `contradicts`, `depends_on`,
`contains`, `part_of`, `precedes`, `equivalent_to`, `observes`, and
`derived_from`. A domain extension has the exact form
`domain:<namespace>:<relation>`. It may not redefine a core relation type.

Direction is one of `directed`, `bidirectional`, or `symmetric`. The validator
owns the relation-type direction table. In v0.1, `equivalent_to` is symmetric;
the other core types are directed unless an explicit later revision changes
their table entry.

`strength`, when present, is a finite number in `[0.0, 1.0]` and represents a
normalized domain-specific association strength. It is never a probability or
a truth value.

`temporal_scope`, when present, is exactly one of:

```text
{ kind: instant, at }
{ kind: interval, valid_from, valid_until }
{ kind: persistent }
{ kind: unknown }
```

Relation lifecycle is `proposed`, `active`, `suspended`, `invalidated`, or
`retired`. Validation state is independently `unverified`, `validated`,
`disputed`, or `rejected`. Invalidated Relations remain addressable for audit;
they are not physically deleted by a canonical graph update.

## 5. Reference and graph invariants

Unit-to-Unit relations are Level 0. Unit-to-Relation and Relation-to-Unit
relations are Level 1. `MAX_RELATION_DEPTH` is 1 in v0.1. A Relation-to-
Relation chain and any deeper recursion are rejected.

The validator MUST enforce:

- unique Unit IDs and Relation IDs within a Graph;
- resolvable source and target references;
- no dangling canonical references;
- valid core or domain relation namespace;
- relation direction, strength, temporal, lifecycle, and validation-state
  contracts;
- the recursion depth restriction; and
- byte-identical canonical output for equivalent input.

Contradictory relations are valid graph data. Conflict detection and resolution
belong to a higher reasoning layer; a graph may contain both `supports` and
`contradicts` relations for the same entities.

## 6. Compatibility and migration

Migration is read-only with respect to legacy sources. It must preserve stable
Unit identity, deterministically generate Relation identity, retain Evidence
and Provenance, produce an explicit reverse projection, and report loss.

Existing RUO-U1 Relations can have Payload, State, or other RUO entities as
endpoints. The v0.1 ReasonEntityRef intentionally permits only `unit` and
`relation`; therefore the adapter reports two independent results:

- `lossless`: the original legacy/RUO representation can be reconstructed;
- `canonical_coverage`: the record was promoted into the v0.1 ReasonGraph.

An unsupported endpoint remains in a registered non-critical compatibility
extension and has `lossless: true, canonical_coverage: false` only when the
exact original record can be reverse-projected. Otherwise `lossless` is false
and the adapter emits an explicit loss record. This preserves existing RUO
semantics without silently claiming that a Payload relation is a Unit relation.

## 7. Transactions and interchange boundary

`GraphTransaction` uses copy-on-write: snapshot, apply proposal, validate the
entire candidate Graph, then commit or restore the original snapshot. A failed
proposal reports zero partial commits and the pre-transaction canonical digest.

The v0.1 MIRP boundary is an in-memory canonical projection only: Unit,
Relation, Unit+Relation, or Graph Fragment. No network transport, distributed
execution, graph database, query language, automatic discovery, neural
learning, probabilistic inference, unrestricted recursion, or N-ary relation
is part of this phase.

## 8. Validation matrix

The implementation uses these fixed identifiers. Tests are introduced in
groups so basic model failures are diagnosed before determinism, migration, or
interchange failures.

| Group | Test ID | Requirement |
| --- | --- | --- |
| Core | RRI-001 | Unit-to-Unit Relation |
| Core | RRI-002 | Directed Relation |
| Core | RRI-003 | Symmetric Relation |
| Core | RRI-004 | Relation Evidence |
| Core | RRI-005 | Relation Provenance |
| Core | RRI-006 | Temporal Relation |
| Core | RRI-007 | Relation Lifecycle |
| Core | RRI-008 | Relation Validation State |
| Core | RRI-009 | Contradictory Relations are retained |
| References | RRI-010 | Unit-to-Relation |
| References | RRI-011 | Illegal recursion rejection |
| References | RRI-012 | Missing Unit rejection |
| References | RRI-013 | Duplicate Unit ID rejection |
| References | RRI-014 | Duplicate Relation ID rejection |
| Compatibility | RRI-015 | Legacy RUO migration |
| Compatibility | RRI-016 | Reverse projection |
| Compatibility | RRI-017 | Migration loss detection |
| Atomicity | RRI-018 | Atomic Graph update |
| Atomicity | RRI-019 | Rollback |
| Determinism | RRI-020 | Canonical serialization |
| Determinism | RRI-021 | Three-run byte identity |
| Determinism | RRI-022 | Input-order independence |
| Determinism | RRI-023 | UnitHash stability |
| Determinism | RRI-024 | RelationHash stability |
| Determinism | RRI-025 | GraphHash stability |
| Extension | RRI-026 | Domain Relation |
| Extension | RRI-027 | Invalid namespace rejection |
| Extension | RRI-028 | MIRP Graph Fragment projection |

Acceptance requires 28/28 RRI tests, Legacy RUO semantic preservation,
atomicity, three byte-identical independent generations, input-order
independence, all invalid fixtures rejected, and the existing RUO regression
suite passing. Golden updates are permitted only for this new feature's
intentional baseline and must be accompanied by this specification and its
changelog entry.

## 9. Evolution gate

After validation, follow-on work may introduce RUO/U1 projection support,
RUO-F1 persistence, Native Runtime behavior, ReasonScript operations, and
MIRP transport. Those are separate specifications and must not be inferred
from this Phase 1 contract.
