# ReasonScript Model G/H Executable RU Benchmark Report

## Environment

- OS: `macOS-26.6.2-arm64-arm-64bit-Mach-O`
- CPU: `arm64`
- ReasonScript: `ReasonScript 0.5.5.15
Install Foundation 1.1
Runtime 0.5.5.15`
- Commit: `07ec0e2df03861e84da4407f65bfc339587e7e84`
- Runtime: `/Users/chigenori/development/ReasonScript/ReasonRuntime/target/release/reason-runtime-host` (release)
- Compiler: `rustc 1.93.1 (01f6ddf75 2026-02-11)`
- Date: `2026-09-19T21:33:15.820251+00:00`

## Dataset and models

The fixed fixture contains 117 cases. Model G uses executable RU `off`; Model H uses `count`. All other runtime settings and IR are identical. Warmup is 3 and samples are 10. Allocation metrics are the runtime's deterministic managed-allocation proxy (VM value slots plus retained ReasonStructure payload), not process heap telemetry.

## Results

- Semantic equivalence: PASS
- RU/lifecycle determinism: PASS
- Invalid lifecycle transitions: 0
- Median RUOR / p90 / max: 3.1285 / 3.2819 / 3.4365
- Median VIO / AOR / PMOR: 1.0000 / 1251.5238 / 1251.5238
- Native / legacy RU ratio: 1.0000 / 0.0000
- Median RUVMR: 0.0370

## Completion judgements

- `1_semantic_equivalence`: PASS
- `2_ru_determinism`: PASS
- `3_lifecycle_determinism`: PASS
- `4_zero_invalid_transition`: PASS
- `5_all_ru_completed`: PASS
- `6_runtime_overhead_target`: FAIL
- `7_vm_overhead_target`: PASS
- `8_allocation_overhead_target`: FAIL
- `9_native_ru_present`: PASS

## Conclusion and next step

RUS gate: **PASS**. Recommended next step: **RU Count Fast Path**.

Reproduce with `python3 scripts/benchmark_executable_ru.py --binary /Users/chigenori/development/ReasonScript/ReasonRuntime/target/release/reason-runtime-host`. Machine-readable evidence is in `artifacts/executable_ru_benchmark/comparison.csv` and `summary.json`; six SVG graphs are in `graphs/`.
