# ReasonScript Model G/H Executable RU Benchmark Report

## Environment

- OS: `macOS-26.6.2-arm64-arm-64bit-Mach-O`
- CPU: `arm64`
- ReasonScript: `ReasonScript 0.5.5.15
Install Foundation 1.1
Runtime 0.5.5.15`
- Commit: `85a1f23569293523cb6335de111ce9afcea278f2`
- Runtime: `/Users/chigenori/development/ReasonScript/ReasonRuntime/target/release/reason-runtime-host` (release)
- Compiler: `rustc 1.93.1 (01f6ddf75 2026-02-11)`
- Date: `2026-09-20T08:39:42.506086+00:00`

## Dataset and models

The fixed Executable RU Microbenchmark Dataset v1 contains 117 cases. Model G uses executable RU `off`; H1 and H2 are frozen Count and Semantic Hash baselines; H3 uses Canonicalization Deduplication / Serializer Elimination in public `count` mode. All other runtime settings and IR are identical. Warmup is 3 and samples are 10; G/H3 order alternates by sample. Allocation metrics are the runtime's deterministic managed-allocation proxy, not process heap telemetry.

## Results

- Semantic equivalence: PASS
- RU/lifecycle determinism and count/full hash equivalence: PASS
- Invalid lifecycle transitions: 0
- Median RUOR H0 / H1 / H2 / H3: 3.1285 / 2.6722 / 1.9476 / 1.9485
- H3 p90 / max: 2.0676 / 2.2410
- Median canonical / total speedup: 0.9507 / 1.3730
- Serializer fallbacks / canonical visits: 0 / 38472
- H3 regressions above H2 +10%: 11
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

RUS gate: **HOLD**. Hash v2 gate: **START**. Recommended next step: **RU Semantic Hash Contract v2 design**. Working tree dirty during measurement: **True**. Runtime binary SHA-256: `fe411b3becd04eafb7b9fb1e85736a4592df3cc244f542364cd6b5ca13024fc2`.

Reproduce with `python3 scripts/benchmark_executable_ru.py --binary /Users/chigenori/development/ReasonScript/ReasonRuntime/target/release/reason-runtime-host`. Machine-readable evidence is in `artifacts/executable_ru_benchmark/comparison.csv` and `summary.json`; six SVG graphs are in `graphs/`.
