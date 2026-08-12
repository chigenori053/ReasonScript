# Phase 15: Native ReasonGraph Query v0.1

## Accepted scope

Phase 15 adds deterministic, read-only Native Runtime queries over a verified
`NativeReasonGraph`. The native results are checked against the existing Python
ReasonGraph query contract.

## Requirements

- Supported queries are `summary`, `entity`, `outgoing`, `incoming`, and
  `neighbors`.
- Each query retains graph ID, graph hash, entity context, deterministic result
  ordering, and a read-only indicator.
- The native result payload must match the Python query result for the same
  canonical RGO-F1 input.
- The CLI boundary is `reason reason-object-graph native-query`.

## Deferred work

Native graph mutation, execution semantics, networked MIRP transport, and
distributed transactions remain outside this phase.
