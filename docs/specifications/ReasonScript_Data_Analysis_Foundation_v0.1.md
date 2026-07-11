# ReasonScript Data Analysis Foundation v0.1

Specification ID: `reasonscript-data-analysis-foundation/0.1`

Status: VALIDATED

Runtime: Python Reference Backend

This repository implements the normative DAF-1 through DAF-8 contract supplied
with this change. The public API is `runtime.data`. It provides immutable typed
tables, explicit and validated schemas, first-class missing values, CSV and JSON
record sources, versioned external tables, selection and transformation,
grouping and aggregation, aggregate/full lineage, stable evidence, resource
limits, and canonical serialization.

The standard functions are represented by `DataBackend`: `load_csv`,
`load_json`, `from_external`, `inspect`, `select`, `filter`, `map`,
`derive_column`, `rename_column`, `count_missing`, `drop_missing`,
`fill_missing`, `group_by`, `aggregate`, `count`, `sum`, `mean`, `median`,
`min`, `max`, `provenance`, `explain`, and `lineage`.

Identifiers are SHA-256 projections of canonical inputs and exclude timestamps,
temporary paths, and output paths. Sources are confined to the declared project
root. The default limits are 100,000 rows, 1,000 columns, 100 MiB files,
1 MiB cells, 10,000 groups, 1,000 operations, 10,000 full-lineage rows, and
100 MiB artifacts. Violations are fatal `DAF-*` diagnostics and never return a
successful partial result.

Data artifacts use the `reasonscript-*-data/0.1` family and project into Reason
IR data units, stable execution-plan steps, bounded simulation events, and
evidence-bearing knowledge. Existing Reason IR and artifact fields remain
unchanged.

DAF-8 is exposed as `analyze_titanic`. It reads `train.csv` directly, derives
`FamilySize` and `IsAlone` row by row, calculates the required profile,
survival, missingness, age, fare, class, sex, and family metrics, and emits the
seven KDA knowledge items with stable DataEvidence. No pre-aggregated Python
values are accepted as input.

Acceptance is defined by `tests/data_analysis/test_data_analysis_foundation.py`
and the repository's canonical `reason ci` pipeline. It covers DAF-AC-001
through DAF-AC-020, including direct 891-row Titanic regression when the
validation dataset is installed.
