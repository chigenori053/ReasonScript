# ReasonScript Model G/H Executable RU Benchmark Report

## Environment

- OS: `macOS-26.6.2-arm64-arm-64bit-Mach-O`
- CPU: `arm64`
- ReasonScript: `ReasonScript 0.5.5.15
Install Foundation 1.1
Runtime 0.5.5.15`
- Commit: `de28b5a14303386ae0070fd7523c8054edb586ff`
- Runtime: `/Users/chigenori/development/ReasonScript/ReasonRuntime/target/release/reason-runtime-host` (release)
- Compiler: `rustc 1.93.1 (01f6ddf75 2026-02-11)`
- Date: `2026-09-19T23:23:17.300443+00:00`

## Dataset and models

The fixed Executable RU Microbenchmark Dataset v1 contains 117 cases. Model G uses executable RU `off`; H1 is the frozen Count Fast Path baseline; H2 uses the Semantic Hash / Canonicalization Fast Path in public `count` mode. All other runtime settings and IR are identical. Warmup is 3 and samples are 10; G/H2 order alternates by sample. Allocation metrics are the runtime's deterministic managed-allocation proxy, not process heap telemetry.

## Results

- Semantic equivalence: PASS
- RU/lifecycle determinism and count/full hash equivalence: PASS
- Invalid lifecycle transitions: 0
- Median RUOR old / H1 / H2: 3.1285 / 2.6722 / 1.9476
- H2 p90 / max: 2.0892 / 2.1714
- Median Semantic Hash speedup: 1.2786
- Median VIO-H2 / AOR-H2: 1.0000 / 1.0000
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

RUS gate: **HOLD**. Recommended next step: **Further RU optimization**. Working tree dirty during measurement: **True**. Runtime binary SHA-256: `201e7ca73ad1fbf273cc949614048539527e5e6a7db720462646c7b6d9931d7c`.

Reproduce with `python3 scripts/benchmark_executable_ru.py --binary /Users/chigenori/development/ReasonScript/ReasonRuntime/target/release/reason-runtime-host`. Machine-readable evidence is in `artifacts/executable_ru_benchmark/comparison.csv` and `summary.json`; six SVG graphs are in `graphs/`.
