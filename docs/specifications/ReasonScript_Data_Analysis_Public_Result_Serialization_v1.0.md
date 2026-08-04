# ReasonScript Data Analysis Public Result Serialization v1.0

Status: VALIDATED

Specification ID: `reasonscript-data-analysis-public-result-serialization/1.0`

`runtime.data.titanic.analyze_titanic` returns a deterministic, JSON-safe public result with schema version
`reasonscript-titanic-analysis-result/1.0`. Runtime `Table` and `DataBackend` values are available only through
`analyze_titanic_execution`. Public results contain stable backend metadata, dataset and table summaries,
metrics, Knowledge, Evidence, and Diagnostics. Absolute paths, runtime identities, timestamps, and run IDs are
excluded. The normative JSON Schema is `schemas/titanic_analysis_result.schema.json`.
