# ReasonScript Model G/H Executable RU Benchmark Report

## Environment

- OS: `macOS-26.6.2-arm64-arm-64bit-Mach-O`
- CPU: `arm64`
- ReasonScript: `ReasonScript 0.5.5.15
Install Foundation 1.1
Runtime 0.5.5.15`
- Commit: `11ba735aef9046b02d5cb6673505a83c268075a4`
- Runtime: `/Users/chigenori/development/ReasonScript/ReasonRuntime/target/release/reason-runtime-host` (release)
- Compiler: `rustc 1.93.1 (01f6ddf75 2026-02-11)`
- Date: `2026-09-19T21:52:57.407018+00:00`

## Dataset and models

The fixed Executable RU Microbenchmark Dataset v1 contains 117 cases. Model G uses executable RU `off`; Model H-fast uses the optimized public `count` mode. H-old values come from the frozen pre-optimization artifact. All other runtime settings and IR are identical. Warmup is 3 and samples are 10; G/H-fast order alternates by sample. Allocation metrics are the runtime's deterministic managed-allocation proxy (VM value slots plus retained ReasonStructure payload), not process heap telemetry.

## Results

- Semantic equivalence: PASS
- RU/lifecycle determinism and count/full hash equivalence: PASS
- Invalid lifecycle transitions: 0
- Median RUOR old / fast: 3.1285 / 2.6722
- Fast p90 / max: 2.8094 / 2.8763
- Median Fast Path speedup: 1.1283
- Median VIO-fast / AOR-fast: 1.0000 / 1.0000
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
- `8_allocation_overhead_target`: PASS
- `9_native_ru_present`: PASS
- `10_count_full_metrics_equal`: PASS
- `11_count_full_hash_equal`: PASS

## Conclusion and next step

RUS gate: **HOLD**. Recommended next step: **Further RU optimization**. Working tree dirty during measurement: **True**. Runtime binary SHA-256: `02aca5a6057df20ee32a18a2098ecf4ce8f04aa6a751bf70468f0b49355493eb`.

Reproduce with `python3 scripts/benchmark_executable_ru.py --binary /Users/chigenori/development/ReasonScript/ReasonRuntime/target/release/reason-runtime-host`. Machine-readable evidence is in `artifacts/executable_ru_benchmark/comparison.csv` and `summary.json`; six SVG graphs are in `graphs/`.
