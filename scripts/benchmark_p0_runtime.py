#!/usr/bin/env python3
"""P0 Runtime Performance re-validation on the ReasonScript_SpecTest v1.3 dataset.

Runs the unchanged v1.3 programs (Model A = Rust trial division, Model B =
ReasonScript wheel-6, Model D = ReasonScript sieve-reasoning) against two
runtime hosts -- `--baseline-host` (the pre-P0 binary) and `--host` (the
optimized binary) -- on identical computation IR, and writes

    <out>/baseline.json      per-case measurements on the baseline host
    <out>/optimized.json     per-case measurements on the optimized host
    <out>/comparison.csv     one row per case, before/after and P0 metrics
    <out>/summary.json       P0 level verdicts (A-F), correlation, determinism

Measurement scope (spec section 23/24): performance runs use trace=off with
reasoning events in COUNT mode; correctness/determinism runs use trace=delta
with FULL events and are executed three times each. Wall time is the host
process (spawn to exit) measured from Python; `runtime_execution_ns` is the
in-process VM time reported by the host itself. CPU time and peak RSS come
from `/usr/bin/time -l` around one additional run.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frontend.computation_ir import lower_program, validate_program  # noqa: E402
from frontend.computation_ir.optimizer import optimize_program  # noqa: E402
from frontend.computation_ir.rust_bridge import find_binary  # noqa: E402
from frontend.language_surface import parse  # noqa: E402

SCHEMA = "reasonscript-p0-runtime-profile/1.0"
TEMPLATES = {"B": "factorize_reasoning.rsn.template", "D": "factorize_sieve_reasoning.rsn.template"}
NA = None


def load_dataset(spectest: Path):
    sys.path.insert(0, str(spectest / "harness"))
    import run_experiment_v1_3 as harness  # type: ignore

    return [(test_id, n, cls) for test_id, n, cls, _stage, _repeats in harness.get_dataset()]


def lower(template: str, n: int) -> dict:
    ir = optimize_program(lower_program(parse(template.replace("__N__", str(n)))))
    errors = validate_program(ir)
    if errors:
        raise ValueError(errors)
    return ir


def request(ir: dict, *, mode: str, event_mode: str, limits: dict) -> str:
    return json.dumps({
        "schema": "reasonscript-runtime-request/1.0", "request_id": "p0-benchmark", "operation": "execute",
        "program": ir,
        "context": {
            "resource_root": str(ROOT), "capabilities": {"filesystem_read": False, "filesystem_write": False, "network": False},
            "limits": limits, "trace": {"enabled": mode != "off", "mode": mode},
            "reasoning": {"semantic_events": True, "event_mode": event_mode},
            "numeric_mode": "compat-reference", "backend": "RuntimeReal",
        },
    })


def run_host(host: Path, payload: str):
    started = time.perf_counter()
    completed = subprocess.run([str(host), "-"], input=payload, capture_output=True, text=True)
    wall_ms = (time.perf_counter() - started) * 1000
    return json.loads(completed.stdout), wall_ms


def run_timed(host: Path, payload: str):
    """One extra run under /usr/bin/time -l for CPU time and peak RSS."""
    completed = subprocess.run(["/usr/bin/time", "-l", str(host), "-"], input=payload, capture_output=True, text=True)
    cpu_ms = peak_mb = None
    for line in completed.stderr.splitlines():
        parts = line.split()
        if line.strip().endswith(" sys") and " user" in line:
            cpu_ms = (float(parts[2]) + float(parts[4])) * 1000
        elif "maximum resident set size" in line:
            peak_mb = float(parts[0]) / 1e6
    return cpu_ms, peak_mb


def signature(out: dict) -> str:
    metadata = out.get("metadata", {})
    return hashlib.sha256(json.dumps({
        "result": out.get("calculation_results"), "ok": out.get("ok"),
        "reasoning_trace": metadata.get("reasoning_trace"), "loop_trace": metadata.get("loop_trace"),
        "candidate_pruned": (metadata.get("runtime_metrics") or {}).get("candidate_pruned_count",
                             sum(e.get("metadata", {}).get("removed_count", 0) for e in metadata.get("reasoning_trace") or [] if e.get("event_type") == "CANDIDATE_PRUNED")),
        "termination_reason": metadata.get("termination_reason", "completed" if out.get("ok") else "runtime_error"),
    }, sort_keys=True).encode()).hexdigest()


def diagnostic_code(out: dict) -> str | None:
    diagnostics = out.get("diagnostics") or []
    return diagnostics[0].get("code") if diagnostics else None


def measure_model(host: Path, ir: dict, samples: int, limits: dict) -> dict:
    perf = request(ir, mode="off", event_mode="count", limits=limits)
    walls, exec_ns, last = [], [], None
    for _ in range(samples):
        out, wall = run_host(host, perf)
        last = out
        walls.append(wall)
        exec_ns.append((out.get("metadata", {}).get("runtime_metrics") or {}).get("runtime_execution_ns"))
    cpu_ms, peak_mb = run_timed(host, perf)
    metrics = last.get("metadata", {}).get("runtime_metrics") or {}
    ok = bool(last.get("ok"))
    result = last.get("calculation_results", {}).get("Result") if ok else None
    # determinism + event sequence: trace=delta, FULL events, three runs
    full = request(ir, mode="delta", event_mode="full", limits=limits)
    signatures, delta_wall, delta_out = [], [], None
    for _ in range(3):
        delta_out, wall = run_host(host, full)
        delta_wall.append(wall)
        signatures.append(signature(delta_out))
    events = delta_out.get("metadata", {}).get("reasoning_trace") or []
    verified = sum(1 for e in events if e["event_type"] == "HYPOTHESIS_VERIFIED")
    rejected = sum(1 for e in events if e["event_type"] == "HYPOTHESIS_REJECTED")
    pruned = sum(e["metadata"].get("removed_count", 0) for e in events if e["event_type"] == "CANDIDATE_PRUNED")
    code = diagnostic_code(last)
    return {
        "ok": ok, "result": result, "diagnostic_code": code,
        "termination_reason": last.get("metadata", {}).get("termination_reason") or ("completed" if ok else ("loop_limit" if code == "RT-LOOP-001" else "runtime_error")),
        "wall_time_ms": statistics.median(walls), "wall_time_ms_samples": walls,
        "runtime_execution_ns": statistics.median([v for v in exec_ns if v is not None]) if any(v is not None for v in exec_ns) else None,
        "cpu_time_ms": cpu_ms, "peak_memory_mb": peak_mb,
        "delta_wall_time_ms": statistics.median(delta_wall),
        "runtime_metrics": metrics,
        "hypothesis_test_count": metrics.get("hypothesis_test_count", verified + rejected),
        "candidate_pruned_count": metrics.get("candidate_pruned_count", pruned),
        "event_sequence": [e["event_type"] for e in events],
        "deterministic": len(set(signatures)) == 1, "signature": signatures[0],
        "trace_bytes": (delta_out.get("metadata", {}).get("runtime_metrics") or {}).get("trace_bytes"),
    }


def measure_rust(binary: Path, n: int, samples: int) -> dict:
    walls, out = [], None
    for _ in range(samples):
        started = time.perf_counter()
        completed = subprocess.run([str(binary), str(n)], capture_output=True, text=True, check=True)
        walls.append((time.perf_counter() - started) * 1000)
        out = json.loads(completed.stdout)
    return {"wall_time_ms": statistics.median(walls), "candidate_tests": out["rust_candidate_tests"], "factors": out["factors"]}


def measure_cli(host: Path, source: str, samples: int) -> float | None:
    """End-to-end `reason run file.rsn --trace=off --json` wall time (v1.3 style)."""
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".rsn", prefix="p0_")
    os.close(fd)
    Path(path).write_text(source)
    env = dict(os.environ, REASONSCRIPT_RUNTIME_HOST=str(host))
    walls = []
    try:
        for _ in range(samples):
            started = time.perf_counter()
            subprocess.run([sys.executable, str(ROOT / "reason"), "run", path, "--trace=off", "--json"], capture_output=True, text=True, cwd=ROOT, env=env)
            walls.append((time.perf_counter() - started) * 1000)
    finally:
        Path(path).unlink(missing_ok=True)
    return statistics.median(walls) if walls else None


def pearson(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    mx = statistics.fmean(p[0] for p in pairs)
    my = statistics.fmean(p[1] for p in pairs)
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    syy = sum((p[1] - my) ** 2 for p in pairs)
    if sxx == 0 or syy == 0:
        return None
    return sum((p[0] - mx) * (p[1] - my) for p in pairs) / math.sqrt(sxx * syy)


def ratio(a, b):
    return round(a / b, 4) if a is not None and b else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spectest", type=Path, default=Path.home() / "development/ReasonScript_SpecTest")
    parser.add_argument("--host", type=Path, default=find_binary())
    parser.add_argument("--baseline-host", type=Path, default=Path.home() / ".reasonscript/versions/0.5.5.15/bin/reason-runtime-host")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--cli-samples", type=int, default=1, help="end-to-end CLI runs per model and case (0 to skip)")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/runtime_profile")
    parser.add_argument("--quick", action="store_true", help="every 6th case only")
    args = parser.parse_args()
    if args.host is None or not args.host.is_file():
        sys.exit("optimized runtime host not found; build ReasonRuntime first")
    rust_bin = args.spectest / "rust_ref/target/release/factorize"
    if not rust_bin.is_file():
        sys.exit(f"Rust reference binary missing: {rust_bin}")
    templates = {model: (args.spectest / "reasonscript" / name).read_text() for model, name in TEMPLATES.items()}
    dataset = load_dataset(args.spectest)
    if args.quick:
        dataset = dataset[::6]
    args.out.mkdir(parents=True, exist_ok=True)

    baseline_cases, optimized_cases, rows = [], [], []
    print(f"{len(dataset)} cases; baseline={args.baseline_host} optimized={args.host}")
    for test_id, n, cls in dataset:
        rust = measure_rust(rust_bin, n, args.samples)
        irs = {model: lower(template, n) for model, template in templates.items()}
        # Baseline: the pre-P0 host with its own defaults (the fixed 10,000 loop cap).
        # Optimized: no loop cap; the wall-time budget is the primary control.
        base = {model: measure_model(args.baseline_host, irs[model], args.samples, {}) for model in irs}
        opt = {model: measure_model(args.host, irs[model], args.samples, {"max_wall_time_ms": 60_000}) for model in irs}
        cli = {model: measure_cli(args.host, templates[model].replace("__N__", str(n)), args.cli_samples) for model in irs} if args.cli_samples else {}
        cli_base = {model: measure_cli(args.baseline_host, templates[model].replace("__N__", str(n)), args.cli_samples) for model in irs} if args.cli_samples else {}
        for model in irs:
            opt[model]["cli_wall_time_ms"] = cli.get(model)
            base[model]["cli_wall_time_ms"] = cli_base.get(model)
        record = lambda models: {"test_id": test_id, "input": n, "input_bits": n.bit_length(), "problem_class": cls, "rust": rust, "models": models}  # noqa: E731
        baseline_cases.append(record(base))
        optimized_cases.append(record(opt))

        d_before, d_after, b_before, b_after = base["D"], opt["D"], base["B"], opt["B"]
        d_steps = (d_after["runtime_metrics"] or {}).get("reasoning_step_count")
        d_tests = d_after["hypothesis_test_count"]
        b_tests = (b_after["runtime_metrics"] or {}).get("loop_iteration_count")
        compression = ratio(b_tests, d_tests)  # wheel-6 candidate tests per sieve hypothesis test
        improvement = ratio(d_before["wall_time_ms"], d_after["wall_time_ms"]) if d_before["ok"] and d_after["ok"] else None
        exec_improvement = ratio(d_before["wall_time_ms"] - (b_before["wall_time_ms"] - b_after["wall_time_ms"]), d_after["wall_time_ms"]) if False else None
        wall_ratio_d_b = ratio(d_after["wall_time_ms"], b_after["wall_time_ms"]) if d_after["ok"] and b_after["ok"] else None
        exec_ratio_d_b = ratio(d_after["runtime_execution_ns"], b_after["runtime_execution_ns"]) if d_after["ok"] and b_after["ok"] else None
        rows.append({
            "test_id": test_id, "input": n, "input_bits": n.bit_length(), "problem_class": cls,
            "correct_before": d_before["ok"] and d_before["result"] is not None and math.prod(rust["factors"]) == n,
            "results_identical": d_before["ok"] and d_after["ok"] and d_before["signature"] == d_after["signature"],
            "events_identical": d_before["event_sequence"] == d_after["event_sequence"] if d_before["ok"] and d_after["ok"] else None,
            "pruned_identical": d_before["candidate_pruned_count"] == d_after["candidate_pruned_count"] if d_before["ok"] and d_after["ok"] else None,
            "deterministic_after": d_after["deterministic"] and b_after["deterministic"],
            "termination_before": d_before["termination_reason"], "termination_after": d_after["termination_reason"],
            "rust_candidate_tests": rust["candidate_tests"], "wheel6_candidate_tests": b_tests,
            "sieve_hypothesis_tests": d_tests, "sieve_reasoning_steps": d_steps,
            "sieve_candidate_pruned": d_after["candidate_pruned_count"],
            "search_compression_ratio": compression,
            "rust_wall_ms": round(rust["wall_time_ms"], 3),
            "wheel6_wall_ms_before": round(b_before["wall_time_ms"], 3) if b_before["ok"] else None,
            "wheel6_wall_ms_after": round(b_after["wall_time_ms"], 3),
            "sieve_wall_ms_before": round(d_before["wall_time_ms"], 3) if d_before["ok"] else None,
            "sieve_wall_ms_after": round(d_after["wall_time_ms"], 3),
            "sieve_exec_ns_after": d_after["runtime_execution_ns"], "wheel6_exec_ns_after": b_after["runtime_execution_ns"],
            "sieve_cpu_ms_after": d_after["cpu_time_ms"], "sieve_peak_mb_after": d_after["peak_memory_mb"],
            "sieve_delta_wall_ms_before": round(d_before["delta_wall_time_ms"], 3) if d_before["ok"] else None,
            "sieve_delta_wall_ms_after": round(d_after["delta_wall_time_ms"], 3),
            "sieve_cli_wall_ms_before": d_before.get("cli_wall_time_ms"), "sieve_cli_wall_ms_after": d_after.get("cli_wall_time_ms"),
            "wheel6_cli_wall_ms_after": b_after.get("cli_wall_time_ms"),
            "sieve_wall_improvement": improvement,
            "sieve_vs_wheel6_wall_ratio": wall_ratio_d_b, "sieve_vs_wheel6_exec_ratio": exec_ratio_d_b,
            "vm_instruction_count": (d_after["runtime_metrics"] or {}).get("vm_instruction_count"),
            "relation_dispatch_count": (d_after["runtime_metrics"] or {}).get("relation_dispatch_count"),
            "predicate_eval_count": (d_after["runtime_metrics"] or {}).get("relation_predicate_eval_count"),
            "allocation_count": (d_after["runtime_metrics"] or {}).get("allocation_count"),
            "allocated_bytes": (d_after["runtime_metrics"] or {}).get("allocated_bytes"),
            "trace_bytes": d_after["trace_bytes"],
            "RER": ratio(rust["candidate_tests"], d_steps),
            "RCRS_ns": ratio(d_after["runtime_execution_ns"], d_steps),
            "CTE": ratio(compression, exec_ratio_d_b) if compression and exec_ratio_d_b else None,
            "POS": ratio((d_after["runtime_metrics"] or {}).get("vm_instruction_count"), d_steps),
        })
        r = rows[-1]
        print(f"  {test_id:28s} sieve {r['sieve_wall_ms_before']}->{r['sieve_wall_ms_after']}ms  wheel6 {r['wheel6_wall_ms_before']}->{r['wheel6_wall_ms_after']}ms  "
              f"compression={compression} identical={r['results_identical']} term={r['termination_before']}->{r['termination_after']}")

    completed_after = [r for r in rows if r["termination_after"] == "completed"]
    loop_limited_before = [r["test_id"] for r in rows if r["termination_before"] in ("loop_limit", "loop_iteration_budget")]
    improvements = [r["sieve_wall_improvement"] for r in rows if r["sieve_wall_improvement"]]
    beats = [r["test_id"] for r in completed_after if r["sieve_vs_wheel6_wall_ratio"] is not None and r["sieve_vs_wheel6_wall_ratio"] <= 1.0]
    beats_exec = [r["test_id"] for r in completed_after if r["sieve_vs_wheel6_exec_ratio"] is not None and r["sieve_vs_wheel6_exec_ratio"] <= 1.0]
    corr = pearson([r["search_compression_ratio"] for r in rows], [r["sieve_wall_improvement"] for r in rows])
    corr_exec = pearson([r["search_compression_ratio"] for r in rows], [r["sieve_vs_wheel6_exec_ratio"] and 1 / r["sieve_vs_wheel6_exec_ratio"] for r in rows])
    median_improvement = statistics.median(improvements) if improvements else None
    summary = {
        "schema": SCHEMA, "cases": len(rows), "samples": args.samples,
        "baseline_host": str(args.baseline_host), "optimized_host": str(args.host),
        "P0-A_no_unnecessary_loop_limit_stop": {"pass": all(r["termination_after"] == "completed" for r in rows), "baseline_loop_limited_cases": loop_limited_before},
        "P0-B_results_events_pruning_identical": {"pass": all(r["results_identical"] and r["events_identical"] and r["pruned_identical"] for r in rows if r["correct_before"]),
                                                  "compared_cases": sum(1 for r in rows if r["correct_before"])},
        "P0-C_sieve_wall_time_minus_20_percent": {"pass": bool(median_improvement and median_improvement >= 1.25), "median_before_over_after": median_improvement,
                                                  "cases_at_or_above_1.25": sum(1 for v in improvements if v >= 1.25), "cases_measured": len(improvements)},
        "P0-D_sieve_at_or_below_wheel6_wall": {"pass": bool(beats), "cases_host_wall": beats, "cases_in_process_execution": beats_exec},
        "P0-E_compression_vs_improvement_correlation": {"pearson_r_wall_improvement": corr, "pearson_r_exec_advantage_over_wheel6": corr_exec, "pass": bool(corr and corr > 0)},
        "P0-F_reasoning_advantage_in_real_time": {"pass": bool(beats) and len(beats) > len(rows) // 2, "cases": len(beats), "of": len(rows)},
        "determinism": {"pass": all(r["deterministic_after"] for r in rows)},
        "median_wheel6_wall_improvement": statistics.median([ratio(b["models"]["B"]["wall_time_ms"], o["models"]["B"]["wall_time_ms"]) for b, o in zip(baseline_cases, optimized_cases) if b["models"]["B"]["ok"]]),
    }
    (args.out / "baseline.json").write_text(json.dumps({"schema": SCHEMA, "host": str(args.baseline_host), "cases": baseline_cases}, indent=1, sort_keys=True))
    (args.out / "optimized.json").write_text(json.dumps({"schema": SCHEMA, "host": str(args.host), "cases": optimized_cases}, indent=1, sort_keys=True))
    with (args.out / "comparison.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
