#!/usr/bin/env python3
"""Model G/H Executable RU benchmark and artifact generator."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend.computation_ir import lower_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.language_surface import parse
from toolchain.artifacts import artifact_manifest, artifact_summary, stable_json

SCHEMA = "reasonscript-executable-ru-benchmark/1.0"
CASES = ROOT / "tests/benchmarks/executable_ru/cases.json"
DEFAULT_OUT = ROOT / "artifacts/executable_ru_benchmark"
OLD_COMPARISON = DEFAULT_OUT / "count_old_baseline.csv"
OLD_SUMMARY = DEFAULT_OUT / "count_old_baseline.json"
H1_COMPARISON = DEFAULT_OUT / "count_fast_path_baseline.csv"
H1_SUMMARY = DEFAULT_OUT / "count_fast_path_baseline.json"
H2_COMPARISON = DEFAULT_OUT / "semantic_hash_baseline.csv"
H2_SUMMARY = DEFAULT_OUT / "semantic_hash_baseline.json"
REPORT = ROOT / "docs/reports/ReasonScript_Model_G_H_Executable_RU_Benchmark_Report.md"
CLASSES = (
    "prime", "semiprime", "composite", "highly_composite", "repeated_factor",
    "small_search_space", "medium_search_space", "large_search_space",
    "high_compression", "low_compression", "early_termination", "long_search",
)
METRICS = (
    "runtime_execution_ns", "vm_instruction_count", "branch_count", "allocation_count",
    "allocated_bytes", "peak_live_bytes", "loop_iterations", "semantic_reasoning_steps",
)
RU_METRICS = (
    "ru_created_count", "ru_activated_count", "ru_executed_count", "ru_verified_count",
    "ru_rejected_count", "ru_completed_count", "ru_lifecycle_transition_count",
    "ru_invalid_transition_count", "ru_hypothesis_count", "ru_verification_count",
    "ru_constraint_derivation_count", "ru_goal_evaluation_count",
    "ru_termination_check_count", "ru_native_count", "ru_legacy_adapter_count",
    "ru_evidence_created_count", "ru_evidence_attached_count",
)


def fixed_cases() -> list[dict]:
    """Return the deterministic fixture source; randomness is never used."""
    cases: list[dict] = []
    for index in range(117):
        problem_class = CLASSES[index % len(CLASSES)]
        width = 6 + (index * 7) % 43
        n = 10_007 + index * 2310
        if problem_class == "semiprime":
            n = (101 + index) * (103 + index)
        elif problem_class in {"composite", "repeated_factor"}:
            n = (24 + index) ** 2
        elif problem_class == "highly_composite":
            n = 720_720 * (index + 1)
        candidates = list(range(2, 2 + width))
        cases.append({
            "test_id": f"case_{index + 1:03d}_{problem_class}",
            "N": n,
            "problem_class": problem_class,
            "search_space_target": width,
            "compression_level": "high" if index % 3 == 0 else "medium" if index % 3 == 1 else "low",
            "candidates": candidates,
            "expected_result": sum(n % value == 0 for value in candidates),
        })
    replacements = (
        (0, "highly_composite_24b", 24_000_000_000, "highly_composite", 48),
        (1, "synthetic_sqrt1000000_k6", 999_983_000_289, "high_compression", 6),
        (2, "synthetic_sqrt1000000_k8", 999_966_000_289, "high_compression", 8),
    )
    for index, test_id, n, problem_class, width in replacements:
        candidates = list(range(2, 2 + width))
        cases[index].update(
            test_id=test_id, N=n, problem_class=problem_class,
            search_space_target=1_000_000, compression_level="high",
            candidates=candidates, expected_result=sum(n % value == 0 for value in candidates),
        )
    return cases


def validate_cases(cases: list[dict]) -> None:
    if len(cases) != 117:
        raise ValueError(f"dataset must contain 117 cases, got {len(cases)}")
    ids = [case["test_id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate test_id")
    required = set(CLASSES)
    present = {case["problem_class"] for case in cases}
    if not required <= present:
        raise ValueError(f"missing problem classes: {sorted(required - present)}")
    for case in cases:
        if case["N"] <= 1 or not case["candidates"]:
            raise ValueError(f"invalid case: {case['test_id']}")
        actual = sum(case["N"] % value == 0 for value in case["candidates"])
        if actual != case["expected_result"]:
            raise ValueError(f"invalid result oracle: {case['test_id']}")


def source_for(case: dict) -> str:
    rows = ", ".join(f"Candidate {{ value: {value} }}" for value in case["candidates"])
    return f"""module Benchmark {{
  struct Candidate {{ value: int }}
  calculation Answer -> int {{
    let candidates = [{rows}]
    let kept = relation.filter(candidates, candidate.value > 1 && {case['N']} % candidate.value == 0)
    result = kept.length
  }}
}}"""


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] if low == high else ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def median_metrics(runs: list[dict]) -> dict:
    missing = [name for name in METRICS if any(name not in run for run in runs)]
    if missing:
        raise ValueError(f"runtime metric missing: {', '.join(missing)}")
    return {name: statistics.median(run[name] for run in runs) for name in METRICS}


def execute(ir: dict, binary: Path, mode: str) -> tuple[dict, dict, dict]:
    outcome = run_ir(
        ir, binary=binary, executable_reason_units=mode, trace_enabled=False,
        semantic_events=True, benchmark_metrics=True,
        limits={"max_loop_iterations": 2_000_000},
    )
    if not outcome.ok:
        raise RuntimeError(f"{outcome.error_code}: {outcome.error_message}")
    metrics = outcome.metadata.get("runtime_metrics", {})
    return outcome.calculation_results, metrics, outcome.metadata.get("reason_unit_trace", {})


def benchmark_case(case: dict, binary: Path, warmup: int, samples: int, old: dict | None = None, h1: dict | None = None, h2: dict | None = None) -> dict:
    ir = lower_program(parse(source_for(case)))
    for _ in range(warmup):
        execute(ir, binary, "off")
        execute(ir, binary, "count")
    runs_g: list[dict] = []
    runs_h: list[dict] = []
    result_g = result_h = None
    trace_h: dict = {}
    for sample in range(samples):
        order = ("off", "count") if sample % 2 == 0 else ("count", "off")
        measured = {mode: execute(ir, binary, mode) for mode in order}
        result_g, metrics_g, _ = measured["off"]
        result_h, metrics_h, trace_h = measured["count"]
        runs_g.append(metrics_g)
        runs_h.append(metrics_h)
    result_full, metrics_full, trace_full = execute(ir, binary, "full")
    g, h = median_metrics(runs_g), median_metrics(runs_h)
    missing_ru = [name for name in RU_METRICS if name not in runs_h[-1]]
    if missing_ru:
        raise ValueError(f"RU metric missing: {', '.join(missing_ru)}")
    row = {
        "test_id": case["test_id"], "problem_class": case["problem_class"], "N": case["N"],
        "sqrt_N": math.isqrt(case["N"]), "compression_level": case["compression_level"],
        "status": "pass", "error_code": "", "runtime_G": g["runtime_execution_ns"],
        "runtime_H": h["runtime_execution_ns"], "RUOR": ratio(h["runtime_execution_ns"], g["runtime_execution_ns"]),
        "vm_instr_G": g["vm_instruction_count"], "vm_instr_H": h["vm_instruction_count"],
        "VIO": ratio(h["vm_instruction_count"], g["vm_instruction_count"]),
        "allocation_G": g["allocated_bytes"], "allocation_H": h["allocated_bytes"],
        "AOR": ratio(h["allocated_bytes"], g["allocated_bytes"]),
        "peak_live_G": g["peak_live_bytes"], "peak_live_H": h["peak_live_bytes"],
        "PMOR": ratio(h["peak_live_bytes"], g["peak_live_bytes"]),
        "loop_iterations_G": g["loop_iterations"], "loop_iterations_H": h["loop_iterations"],
        "semantic_steps_G": g["semantic_reasoning_steps"], "semantic_steps_H": h["semantic_reasoning_steps"],
    }
    row.update({f"{name.removesuffix('_count')}_H": runs_h[-1][name] for name in RU_METRICS})
    created = runs_h[-1]["ru_created_count"]
    executed = runs_h[-1]["ru_executed_count"]
    row.update(
        NRR=ratio(runs_h[-1]["ru_native_count"], created),
        LRR=ratio(runs_h[-1]["ru_legacy_adapter_count"], created),
        RUVMR=ratio(h["vm_instruction_count"], executed),
        result_equal=result_g == result_h == {"Answer": case["expected_result"]},
        hypothesis_hash_equal=runs_g[-1].get("hypothesis_sequence_hash") == runs_h[-1].get("hypothesis_sequence_hash"),
        ru_sequence_hash=trace_h.get("ru_sequence_hash"), ru_lifecycle_hash=trace_h.get("ru_lifecycle_hash"),
        runtime_H_old=float(old["runtime_H"]) if old else None,
        RUOR_old=float(old["RUOR"]) if old else None,
        AOR_old=float(old["AOR"]) if old else None,
        runtime_H1=float(h1["runtime_H_fast"]) if h1 else None,
        RUOR_H1=float(h1["RUOR_fast"]) if h1 else None,
        runtime_H_fast=h["runtime_execution_ns"],
        runtime_H2=float(h2["runtime_H2"]) if h2 else None,
        runtime_H3=h["runtime_execution_ns"],
        RUOR_fast=ratio(h["runtime_execution_ns"], g["runtime_execution_ns"]),
        RUOR_H2=float(h2["RUOR_H2"]) if h2 else None,
        RUOR_H3=ratio(h["runtime_execution_ns"], g["runtime_execution_ns"]),
        FastPathSpeedup=ratio(float(old["runtime_H"]), h["runtime_execution_ns"]) if old else None,
        SemanticHashSpeedup=ratio(float(h1["runtime_H_fast"]), h["runtime_execution_ns"]) if h1 else None,
        CanonicalFastSpeedup=ratio(float(h2["runtime_H2"]), h["runtime_execution_ns"]) if h2 else None,
        TotalRUSpeedup=ratio(float(old["runtime_H"]), h["runtime_execution_ns"]) if old else None,
        VIO_fast=ratio(h["vm_instruction_count"], g["vm_instruction_count"]),
        allocation_H_fast=h["allocated_bytes"], AOR_fast=ratio(h["allocated_bytes"], g["allocated_bytes"]),
        ru_sequence_hash_count=trace_h.get("ru_sequence_hash"),
        ru_sequence_hash_full=trace_full.get("ru_sequence_hash"),
        ru_lifecycle_hash_count=trace_h.get("ru_lifecycle_hash"),
        ru_lifecycle_hash_full=trace_full.get("ru_lifecycle_hash"),
        ru_hash_bytes=runs_h[-1].get("ru_hash_bytes", 0),
        ru_hash_update_count=runs_h[-1].get("ru_hash_update_count", 0),
        ru_canonical_value_visits=runs_h[-1].get("ru_canonical_value_visits", 0),
        ru_serializer_fallback_count=runs_h[-1].get("ru_serializer_fallback_count", 0),
    )
    comparable = [name for name in RU_METRICS if name in metrics_full]
    row["metrics_equal"] = all(runs_h[-1][name] == metrics_full[name] for name in comparable)
    row["hash_equal"] = (
        row["ru_sequence_hash_count"] == row["ru_sequence_hash_full"]
        and row["ru_lifecycle_hash_count"] == row["ru_lifecycle_hash_full"]
    )
    row["result_equal"] = row["result_equal"] and result_h == result_full
    return row


def determinism(cases: list[dict], binary: Path) -> bool:
    for case in cases[:3]:
        ir = lower_program(parse(source_for(case)))
        traces = [execute(ir, binary, "full")[2] for _ in range(3)]
        for key in ("ru_sequence_hash", "ru_lifecycle_hash"):
            if len({trace[key] for trace in traces}) != 1:
                return False
    return True


def environment(binary: Path) -> dict:
    def command(*args: str) -> str:
        return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False).stdout.strip()
    dirty = bool(command("git", "status", "--porcelain"))
    return {
        "os": platform.platform(), "cpu_architecture": platform.machine(),
        "reasonscript_version": command(str(ROOT / "reason"), "--version"),
        "commit_sha": command("git", "rev-parse", "HEAD"), "runtime_binary_path": str(binary),
        "build_profile": "release" if "/release/" in str(binary) else "debug",
        "compiler_version": command("rustc", "--version"),
        "date": datetime.now(timezone.utc).isoformat(),
        "source_commit": command("git", "rev-parse", "HEAD"),
        "benchmark_commit": command("git", "rev-parse", "HEAD"),
        "working_tree_dirty": dirty,
        "runtime_binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    }


def summarize(rows: list[dict], deterministic: bool, env: dict, warmup: int, samples: int, old_summary: dict | None = None, h1_summary: dict | None = None, h2_summary: dict | None = None) -> dict:
    values = lambda name: [float(row[name]) for row in rows if row[name] is not None]
    total_created = sum(row["ru_created_H"] for row in rows)
    total_native = sum(row["ru_native_H"] for row in rows)
    total_legacy = sum(row["ru_legacy_adapter_H"] for row in rows)
    all_completed = all(row["ru_created_H"] == row["ru_completed_H"] == row["ru_executed_H"] for row in rows)
    judgements = {
        "1_semantic_equivalence": all(row["result_equal"] for row in rows),
        "2_ru_determinism": deterministic, "3_lifecycle_determinism": deterministic,
        "4_zero_invalid_transition": all(row["ru_invalid_transition_H"] == 0 for row in rows),
        "5_all_ru_completed": all_completed,
        "6_runtime_overhead_target": statistics.median(values("RUOR_fast")) <= 1.20 and percentile(values("RUOR_fast"), .9) <= 1.35,
        "7_vm_overhead_target": statistics.median(values("VIO")) <= 1.20,
        "8_allocation_overhead_target": statistics.median(values("AOR_fast")) <= 2.0,
        "9_native_ru_present": all(row["ru_native_H"] > 0 for row in rows),
        "10_count_full_metrics_equal": all(row["metrics_equal"] for row in rows),
        "11_count_full_hash_equal": all(row["hash_equal"] for row in rows),
    }
    return {
        "schema": SCHEMA, "environment": env, "warmup": warmup, "samples": samples,
        "allocation_metric_kind": "deterministic_managed_proxy",
        "cases_total": len(rows), "cases_passed": sum(row["status"] == "pass" for row in rows),
        "semantic_equivalence_pass": judgements["1_semantic_equivalence"],
        "median_runtime_G": statistics.median(values("runtime_G")),
        "median_runtime_H": statistics.median(values("runtime_H")),
        "median_RUOR": statistics.median(values("RUOR_fast")), "p90_RUOR": percentile(values("RUOR_fast"), .9),
        "max_RUOR": max(values("RUOR_fast")), "median_VIO": statistics.median(values("VIO")),
        "median_AOR": statistics.median(values("AOR_fast")), "median_PMOR": statistics.median(values("PMOR")),
        "median_RUOR_old": old_summary.get("median_RUOR") if old_summary else None,
        "median_RUOR_H1": h1_summary.get("median_RUOR_fast") if h1_summary else None,
        "median_RUOR_H2": h2_summary.get("median_RUOR_H2") if h2_summary else None,
        "median_RUOR_H3": statistics.median(values("RUOR_H3")),
        "p90_RUOR_H3": percentile(values("RUOR_H3"), .9),
        "max_RUOR_H3": max(values("RUOR_H3")),
        "median_canonical_fast_speedup": statistics.median(values("CanonicalFastSpeedup")),
        "median_total_ru_speedup": statistics.median(values("TotalRUSpeedup")),
        "serializer_fallback_total": sum(row["ru_serializer_fallback_count"] for row in rows),
        "canonical_value_visits": sum(row["ru_canonical_value_visits"] for row in rows),
        "h3_regression_cases": sum(row["runtime_H3"] > row["runtime_H2"] * 1.10 for row in rows),
        "median_semantic_hash_speedup": statistics.median(values("SemanticHashSpeedup")),
        "median_VIO_H2": statistics.median(values("VIO_fast")),
        "median_AOR_H2": statistics.median(values("AOR_fast")),
        "median_RUOR_fast": statistics.median(values("RUOR_fast")),
        "p90_RUOR_fast": percentile(values("RUOR_fast"), .9),
        "max_RUOR_fast": max(values("RUOR_fast")),
        "median_fast_path_speedup": statistics.median(values("FastPathSpeedup")),
        "median_AOR_fast": statistics.median(values("AOR_fast")),
        "median_VIO_fast": statistics.median(values("VIO_fast")),
        "hash_equivalence": all(row["hash_equal"] for row in rows),
        "lifecycle_equivalence": all(row["ru_lifecycle_hash_count"] == row["ru_lifecycle_hash_full"] for row in rows),
        "median_RUVMR": statistics.median(values("RUVMR")), "total_ru_created": total_created,
        "total_ru_native": total_native, "total_ru_legacy": total_legacy,
        "native_ru_ratio": ratio(total_native, total_created), "legacy_ru_ratio": ratio(total_legacy, total_created),
        "invalid_lifecycle_total": sum(row["ru_invalid_transition_H"] for row in rows),
        "determinism_pass": deterministic, "judgements": judgements,
        "working_tree_dirty": env["working_tree_dirty"], "source_commit": env["source_commit"],
        "benchmark_commit": env["benchmark_commit"], "runtime_binary_sha256": env["runtime_binary_sha256"],
        "performance_gate": "PASS" if statistics.median(values("RUOR_fast")) <= 1.50 else "HOLD" if statistics.median(values("RUOR_fast")) < 2.0 else "FAIL",
        "rus_gate": "PASS" if all(list(judgements.values())[:5]) and statistics.median(values("RUOR_fast")) <= 1.50 else "HOLD",
        "hash_v2_gate": "NOT_NEEDED" if statistics.median(values("RUOR_fast")) <= 1.50 else "START",
        "next_step": "RUS" if statistics.median(values("RUOR_fast")) <= 1.50 else "RU Semantic Hash Contract v2 design",
    }


def write_svg(path: Path, title: str, points: list[tuple[float, float]], x_label: str, y_label: str) -> None:
    width, height, margin = 900, 480, 60
    xs, ys = [point[0] for point in points], [point[1] for point in points]
    x_min, x_max = min(xs), max(xs) or 1
    y_min, y_max = min(ys), max(ys) or 1
    def project(point: tuple[float, float]) -> tuple[float, float]:
        x = margin + (point[0] - x_min) / (x_max - x_min or 1) * (width - 2 * margin)
        y = height - margin - (point[1] - y_min) / (y_max - y_min or 1) * (height - 2 * margin)
        return x, y
    circles = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3"/>' for x, y in map(project, points))
    path.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><style>text{{font:14px sans-serif}}circle{{fill:#2563eb;opacity:.65}}line{{stroke:#111}}</style><text x="{width/2}" y="25" text-anchor="middle">{title}</text><line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}"/><line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}"/>{circles}<text x="{width/2}" y="{height-12}" text-anchor="middle">{x_label}</text><text x="16" y="{height/2}" transform="rotate(-90 16 {height/2})" text-anchor="middle">{y_label}</text></svg>''', encoding="utf-8")


def write_artifacts(rows: list[dict], summary: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    summary.update(
        version="1.0", generator="benchmark_executable_ru.py",
        generated_at=summary["environment"]["date"], language_version="0.5",
    )
    (out / "summary.json").write_text(stable_json(summary), encoding="utf-8")
    graphs = out / "graphs"; graphs.mkdir(exist_ok=True)
    specifications = (
        ("ruor_h2_vs_h3.svg", "RUOR H2 vs H3", [(row["RUOR_H2"], row["RUOR_H3"]) for row in rows], "RUOR H2", "RUOR H3"),
        ("runtime_g_h2_h3.svg", "Runtime G / H2 / H3", [(i * 3 + series, value) for i, row in enumerate(rows) for series, value in enumerate((row["runtime_G"], row["runtime_H2"], row["runtime_H3"]))], "case series", "ns"),
        ("ru_count_vs_h3_ruor.svg", "RU count vs H3 RUOR", [(row["ru_created_H"], row["RUOR_H3"]) for row in rows], "RU count", "RUOR H3"),
        ("canonical_fast_speedup.svg", "Canonical Fast speedup", [(i, row["CanonicalFastSpeedup"]) for i, row in enumerate(rows)], "case", "speedup"),
        ("canonical_visits_vs_runtime.svg", "Canonical visits vs H3 runtime", [(row["ru_canonical_value_visits"], row["runtime_H3"]) for row in rows], "canonical visits", "ns"),
        ("hash_updates_vs_runtime.svg", "Hash updates vs H3 runtime", [(row["ru_hash_update_count"], row["runtime_H3"]) for row in rows], "hash updates", "ns"),
    )
    for name, title, points, x_label, y_label in specifications:
        write_svg(graphs / name, title, points, x_label, y_label)
    filenames = ["comparison.csv", "summary.json", "count_old_baseline.csv", "count_old_baseline.json", "count_fast_path_baseline.csv", "count_fast_path_baseline.json", "semantic_hash_baseline.csv", "semantic_hash_baseline.json", *(f"graphs/{item[0]}" for item in specifications)]
    manifest = artifact_manifest(filenames, generator="benchmark_executable_ru.py", language_version="0.5")
    artifact_info = artifact_summary(filenames, generator="benchmark_executable_ru.py", language_version="0.5")
    (out / "artifact_manifest.json").write_text(stable_json(manifest), encoding="utf-8")
    (out / "artifact_summary.json").write_text(stable_json(artifact_info), encoding="utf-8")


def write_report(summary: dict, out: Path) -> None:
    env, judgements = summary["environment"], summary["judgements"]
    verdicts = "\n".join(f"- `{name}`: {'PASS' if value else 'FAIL'}" for name, value in judgements.items())
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(f"""# ReasonScript Model G/H Executable RU Benchmark Report

## Environment

- OS: `{env['os']}`
- CPU: `{env['cpu_architecture']}`
- ReasonScript: `{env['reasonscript_version']}`
- Commit: `{env['commit_sha']}`
- Runtime: `{env['runtime_binary_path']}` ({env['build_profile']})
- Compiler: `{env['compiler_version']}`
- Date: `{env['date']}`

## Dataset and models

The fixed Executable RU Microbenchmark Dataset v1 contains {summary['cases_total']} cases. Model G uses executable RU `off`; H1 and H2 are frozen Count and Semantic Hash baselines; H3 uses Canonicalization Deduplication / Serializer Elimination in public `count` mode. All other runtime settings and IR are identical. Warmup is {summary['warmup']} and samples are {summary['samples']}; G/H3 order alternates by sample. Allocation metrics are the runtime's deterministic managed-allocation proxy, not process heap telemetry.

## Results

- Semantic equivalence: {'PASS' if summary['semantic_equivalence_pass'] else 'FAIL'}
- RU/lifecycle determinism and count/full hash equivalence: {'PASS' if summary['determinism_pass'] and summary['hash_equivalence'] else 'FAIL'}
- Invalid lifecycle transitions: {summary['invalid_lifecycle_total']}
- Median RUOR H0 / H1 / H2 / H3: {summary['median_RUOR_old']:.4f} / {summary['median_RUOR_H1']:.4f} / {summary['median_RUOR_H2']:.4f} / {summary['median_RUOR_H3']:.4f}
- H3 p90 / max: {summary['p90_RUOR_H3']:.4f} / {summary['max_RUOR_H3']:.4f}
- Median canonical / total speedup: {summary['median_canonical_fast_speedup']:.4f} / {summary['median_total_ru_speedup']:.4f}
- Serializer fallbacks / canonical visits: {summary['serializer_fallback_total']} / {summary['canonical_value_visits']}
- H3 regressions above H2 +10%: {summary['h3_regression_cases']}
- Median VIO-H3 / AOR-H3: {summary['median_VIO_fast']:.4f} / {summary['median_AOR_fast']:.4f}
- Native / legacy RU ratio: {summary['native_ru_ratio']:.4f} / {summary['legacy_ru_ratio']:.4f}
- Median RUVMR: {summary['median_RUVMR']:.4f}

## Completion judgements

{verdicts}

## Conclusion and next step

RUS gate: **{summary['rus_gate']}**. Hash v2 gate: **{summary['hash_v2_gate']}**. Recommended next step: **{summary['next_step']}**. Working tree dirty during measurement: **{summary['working_tree_dirty']}**. Runtime binary SHA-256: `{summary['runtime_binary_sha256']}`.

Reproduce with `python3 scripts/benchmark_executable_ru.py --binary {env['runtime_binary_path']}`. Machine-readable evidence is in `{out.relative_to(ROOT)}/comparison.csv` and `summary.json`; six SVG graphs are in `graphs/`.
""", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--quick", action="store_true", help="run three cases with one sample for harness validation")
    parser.add_argument("--write-cases", action="store_true", help="regenerate the deterministic cases fixture")
    args = parser.parse_args()
    if args.write_cases:
        CASES.parent.mkdir(parents=True, exist_ok=True)
        CASES.write_text(json.dumps(fixed_cases(), indent=2) + "\n", encoding="utf-8")
        return 0
    cases = json.loads(CASES.read_text(encoding="utf-8")); validate_cases(cases)
    with OLD_COMPARISON.open(newline="", encoding="utf-8") as stream:
        old_rows = {row["test_id"]: row for row in csv.DictReader(stream)}
    old_summary = json.loads(OLD_SUMMARY.read_text(encoding="utf-8"))
    with H1_COMPARISON.open(newline="", encoding="utf-8") as stream:
        h1_rows = {row["test_id"]: row for row in csv.DictReader(stream)}
    h1_summary = json.loads(H1_SUMMARY.read_text(encoding="utf-8"))
    with H2_COMPARISON.open(newline="", encoding="utf-8") as stream:
        h2_rows = {row["test_id"]: row for row in csv.DictReader(stream)}
    h2_summary = json.loads(H2_SUMMARY.read_text(encoding="utf-8"))
    binary = (args.binary or find_binary())
    if binary is None:
        parser.error("runtime host not found; build ReasonRuntime first")
    binary = binary.resolve()
    selected = cases[:3] if args.quick else cases
    warmup, samples = (0, 1) if args.quick else (args.warmup, args.samples)
    if warmup < 0 or samples < 1:
        parser.error("warmup must be non-negative and samples must be positive")
    rows = [benchmark_case(case, binary, warmup, samples, old_rows.get(case["test_id"]), h1_rows.get(case["test_id"]), h2_rows.get(case["test_id"])) for case in selected]
    deterministic = determinism(selected, binary)
    summary = summarize(rows, deterministic, environment(binary), warmup, samples, old_summary, h1_summary, h2_summary)
    write_artifacts(rows, summary, args.out.resolve())
    if not args.quick:
        write_report(summary, args.out.resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    mandatory = ("1_semantic_equivalence", "2_ru_determinism", "3_lifecycle_determinism", "4_zero_invalid_transition", "5_all_ru_completed", "10_count_full_metrics_equal", "11_count_full_hash_equal")
    return 0 if all(summary["judgements"][name] for name in mandatory) else 1


if __name__ == "__main__":
    raise SystemExit(main())
