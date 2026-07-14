# ReasonScript Data Analysis Foundation v0.1

## Status

VALIDATED

## Added

- Added the immutable typed Table, Row, Column, Schema, DataType, Missing, and DatasetRef model.
- Added standard-library CSV, JSON-record, and versioned external-table loading.
- Added missing-value, table transformation, group-by, and numeric aggregation functions.
- Added deterministic dataset, row, column, table, operation, aggregation, and evidence identity.
- Added aggregate/full provenance, Knowledge evidence integration, resource limits, and data artifacts.
- Added direct Titanic CSV regression with FamilySize and IsAlone derivation and seven KDA knowledge items.
- Added JSON Schemas and unit, integration, negative, determinism, and external-project regression tests.

## Compatibility

The feature is isolated under `runtime.data`; existing source behavior and
existing Reason IR and artifact names are unchanged. The package distribution
now includes `runtime*`. No third-party runtime dependency was added.

## Validation

The canonical validation command is `reason ci --json`. Detailed results are
recorded in the completion report and `agent_report.json`.
