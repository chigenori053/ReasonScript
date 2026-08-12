# MRA RUO / ReasonRelation Phase 17

## Added

- A capability-gated `.rsn` ReasonGraph binding and query source subset.
- Native/Python query-result parity during source execution.
- `reason reason-object-graph source-check` and `source-run` commands.

## Compatibility

This adds an isolated read-only language boundary and does not alter generic
ReasonScript parsing, `reason run`, RGO-F1, or RUO behavior.
