# Phase 16: Native ReasonGraph Metadata Transaction v0.1

## Accepted scope

Phase 16 introduces the first native mutation boundary for RGO-F1. It performs
an atomic, copy-on-write `graph_updates.metadata` transaction and compares its
outcome with the Phase 13 Python transaction contract.

## Requirements

- The transaction requires a current graph hash and a `ruo:transaction:` ID.
- Only a complete replacement `graph_updates.metadata` map is accepted.
- A stale or invalid proposal is rejected without changing source bytes.
- A successful update writes a complete canonical RGO-F1 file through atomic
  publication and reports the new graph hash.
- Unit, Relation, root, provenance, lifecycle, and identity mutation are not
  permitted in this phase.

## Deferred work

Native Unit/Relation mutation, broader graph updates, ReasonScript operations,
networked MIRP transport, distributed transactions, and execution semantics
remain outside this phase.
