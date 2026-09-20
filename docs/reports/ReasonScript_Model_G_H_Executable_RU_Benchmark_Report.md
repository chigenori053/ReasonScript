# ReasonScript Model G/H Executable RU Benchmark Report

## Environment

- OS: `macOS-26.6.2-arm64-arm-64bit-Mach-O`
- CPU: `arm64`
- ReasonScript: `ReasonScript 0.5.5.15
Install Foundation 1.1
Runtime 0.5.5.15`
- Commit: `83bb01e5d3fb6fddb333ba8c5983775db3a93a1c`
- Runtime: `/Users/chigenori/development/ReasonScript/ReasonRuntime/target/release/reason-runtime-host` (release)
- Compiler: `rustc 1.93.1 (01f6ddf75 2026-02-11)`
- Date: `2026-09-20T08:56:56.004838+00:00`

## Dataset and models

The fixed Executable RU Microbenchmark Dataset v1 contains 117 cases. Model G uses executable RU `off`; H1 and H2 are frozen Count and Semantic Hash baselines; H3 uses Canonicalization Deduplication / Serializer Elimination in public `count` mode. All other runtime settings and IR are identical. Warmup is 3 and samples are 10; G/H3 order alternates by sample. Allocation metrics are the runtime's deterministic managed-allocation proxy, not process heap telemetry.

## Results

- Semantic equivalence: PASS
- RU/lifecycle determinism and count/full hash equivalence: PASS
- Invalid lifecycle transitions: 0
- Median RUOR H0 / H1 / H2 / H3: 3.1285 / 2.6722 / 1.9476 / 1.8971
- H3 p90 / max: 2.0374 / 2.1508
- Median canonical / total speedup: 0.9141 / 1.3177
- Serializer fallbacks / canonical visits: 0 / 38472
- H3 regressions above H2 +10%: 48
- Median VIO-H3 / AOR-H3: 1.0000 / 1.0000
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

RUS gate: **HOLD**. Hash v2 gate: **START**. Recommended next step: **RU Semantic Hash Contract v2 design**. Working tree dirty during measurement: **True**. Runtime binary SHA-256: `4c102998230e7e3418b7b6218f3608d0fd1d671ee247d5a910505ff3116cb3f2`.

Reproduce with `python3 scripts/benchmark_executable_ru.py --binary /Users/chigenori/development/ReasonScript/ReasonRuntime/target/release/reason-runtime-host`. Machine-readable evidence is in `artifacts/executable_ru_benchmark/comparison.csv` and `summary.json`; six SVG graphs are in `graphs/`.
