# ReasonScript Conformance Framework Specification v0.1

Status: Implemented Draft  
ABI: `reason-ir/0.1`

## Purpose

The framework verifies that the ReasonScript compiler boundary, SDK DTOs, and
reference Runtime interpret the same ABI and fixtures deterministically.
Network protocols, storage engines, distributed runtimes, and external service
adapters are outside this version.

## Principles

1. One ABI: every suite targets `reason-ir/0.1`.
2. Fixture driven: inputs and expected semantic projections are versioned.
3. Language neutral: JSON wire data is the comparison boundary.
4. Version aware: unknown explicit ABI versions are rejected.
5. Deterministic: repeated execution must produce the same normalized result.
6. Evidence based: missing toolchains and skipped tests never count as passes.

## Layers

| Layer | Name | Required evidence |
|---|---|---|
| 0 | Schema | JSON Schema, required fields, types, version, semantic ABI constraints |
| 1 | DTO | serialization, deserialization, round trip, metadata, uint64 timestamps |
| 2 | Runtime | ReasonIR input produces the expected normalized InferenceResult |
| 3 | Transaction | prepare, validate, commit, rollback, audit records, trace consistency |
| 4 | Platform | all SDK adapters return equivalent normalized wire DTOs and semantics |

The public DTO set is `ReasonIR`, `ExecutionPlan`, `StateDelta`,
`InferenceResult`, `Trace`, and `TransactionRecord`. `PreparedDelta` is
Runtime-internal.

## Fixtures

Core fixtures are stored in `fixtures/valid`, ABI rejection fixtures in
`fixtures/invalid`, and transaction fixtures in
`conformance/fixtures/transactions`. The versioned catalog and expected Core
semantic results are in `conformance/fixtures/manifest.json`.

Future fixtures (`memoryspace_query`, `dbm_planning`,
`worldmodel_branching`, and `llm_tool_use`) require future Runtime capability
and are not certification evidence for v0.1.

## Certification

Levels are cumulative from Schema Compatible (Level 0) through Full Compatible
(Level 4). The normative machine-readable model is
`conformance/certification/model.json`.

Full Compatible requires executable Rust, Python, TypeScript, Go, and Java
adapters in the same Layer 4 run. Source declarations or skipped toolchains
are insufficient.

## Execution

```sh
python3 conformance/run_conformance.py
```

The command writes:

- `conformance/reports/conformance_results_v0.1.json`
- `conformance/reports/Conformance_Report_v0.1.md`

## Success Criteria

The framework implementation is complete when all five layer suites can run,
the certification decision is generated from evidence, and failures or
unavailable SDKs are reported without false promotion. Platform-wide Full
Compatible status is a separate certification outcome and is granted only
when every SDK satisfies all cumulative requirements.
