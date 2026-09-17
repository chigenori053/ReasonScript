#!/usr/bin/env python3
"""SpecTest v1.3 / Experiment D, using only Rust for execution.

The v1.2 source fixtures were not supplied. C-old reconstructs its specified
array.append/filter_ne/full-snapshot behavior on a bounded comparison case.
All construction/filter timings include the native host process boundary;
the frontend is lowered once, outside the measured region.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frontend.computation_ir import lower_program, validate_program
from frontend.computation_ir.optimizer import optimize_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.language_surface import parse

SCHEMA = "reasonscript-relation-state-benchmark/1.0"
DECLARATIONS = """
    struct Candidate {
        value: int
    }
    struct Report {
        factors: [int]
        candidate_tests: int
        termination: string
    }
"""


def program(body: str):
    ir = optimize_program(lower_program(parse(f"module ExperimentD {{\n{DECLARATIONS}\n calculation Answer {{\n{body}\n }}\n}}")))
    errors = validate_program(ir)
    if errors:
        raise ValueError(errors)
    return ir


def construction(n: int, *, filtering: bool = False):
    body = f"""
        let builder = array.builder()
        let i = 1
        while i <= {n} {{
            builder.append(Candidate {{ value: i }})
            i = i + 1
        }}
        let rows = builder.finish()
    """
    if filtering:
        body += """
        let factor = 3
        let kept = relation.filter(rows, candidate.value % factor != 0)
        result = kept.length
        """
    else:
        body += "result = rows.length\n"
    return program(body)


def filter_only(n: int):
    rows = ", ".join(f"Candidate {{ value: {i} }}" for i in range(1, n + 1))
    return program(f"""
        let rows = [{rows}]
        let factor = 3
        result = relation.filter(rows, row.value % factor != 0).length
    """)


def factorization(n: int, model: str):
    prefix = f"""
        let remaining = {n}
        let factors = array.builder()
        let tests = 0
    """
    if model == "B":
        body = """
        let p = 2
        let step = 2
        while p * p <= remaining {
            tests = tests + 1
            while remaining % p == 0 {
                factors.append(p)
                remaining = int(remaining / p)
            }
            if p == 2 {
                p = 3
            } elif p == 3 {
                p = 5
            } else {
                p = p + step
                step = 6 - step
            }
        }
        """
    else:
        if model == "C-old":
            body = "let candidates: [Candidate] = []\n"
            append = "candidates = array.append(candidates, Candidate { value: generated })"
            seeds = """
                candidates = array.append(candidates, Candidate { value: 2 })
                candidates = array.append(candidates, Candidate { value: 3 })
            """
        else:
            body = "let builder = array.builder()\n"
            append = "builder.append(Candidate { value: generated })"
            seeds = """
                builder.append(Candidate { value: 2 })
                builder.append(Candidate { value: 3 })
            """
        body += seeds + f"""
        let generated = 5
        let step = 2
        while generated * generated <= {n} {{
            {append}
            generated = generated + step
            step = 6 - step
        }}
        """
        if model == "D":
            body += "let candidates = builder.finish()\n"
        body += """
        let cursor = 0
        while cursor < candidates.length {
            let p = candidates[cursor].value
            if p * p > remaining {
                break
            }
            tests = tests + 1
            if remaining % p == 0 {
                while remaining % p == 0 {
                    factors.append(p)
                    remaining = int(remaining / p)
                }
                reasoning.event("HYPOTHESIS_VERIFIED", p, remaining)
        """
        if model == "D":
            body += """
                candidates = relation.filter(candidates, candidate.value > p && candidate.value % p != 0)
                cursor = 0
            } else {
                cursor = cursor + 1
            }
        }
            """
        else:
            body += """
            }
            candidates = relation.filter_ne(candidates, "value", p)
        }
            """
    return program(prefix + body + """
        if remaining > 1 {
            factors.append(remaining)
        }
        reasoning.event("TERMINATION_INFERRED", "factorization_complete", remaining)
        let sequence = factors.finish()
        result = Report { factors: sequence, candidate_tests: tests, termination: "factorization_complete" }
    """)


def measured(ir: dict, samples: int, mode: str = "off"):
    durations = []
    signatures = []
    last = None
    for _ in range(samples):
        started = time.perf_counter()
        last = run_ir(ir, trace_enabled=True, trace_config={"mode": mode},
                      limits={"max_loop_iterations": 100_000})
        durations.append(time.perf_counter() - started)
        if not last.ok:
            raise RuntimeError((last.error_code, last.error_message))
        signatures.append(hashlib.sha256(json.dumps({
            "answer": last.calculation_results,
            "events": last.metadata["reasoning_trace"],
            "state_trace": last.metadata["loop_trace"],
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
    assert last is not None
    memory = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return {
        "median_seconds": statistics.median(durations),
        "durations_seconds": durations,
        "result": last.calculation_results["Answer"],
        "metrics": last.metadata["runtime_metrics"],
        "trace_diagnostics": last.metadata["trace_diagnostics"],
        "deterministic": len(set(signatures)) == 1,
        "signature": signatures[0],
        "children_high_water_bytes": memory if sys.platform == "darwin" else memory * 1024,
    }


def benchmark(samples: int = 3, *, quick: bool = False):
    if find_binary() is None:
        raise FileNotFoundError("build reason-runtime-host before benchmarking")
    sizes = [100, 500, 1000] if quick else [100, 500, 1000, 2000, 4000, 5000, 8000, 10000]
    scaling = []
    for n in sizes:
        build = measured(construction(n), samples)
        filtering = measured(filter_only(n), samples)
        total = measured(construction(n, filtering=True), samples)
        trace = measured(construction(n, filtering=True), samples, "delta")
        if build["result"] != n or total["result"] != n - n // 3 or filtering["result"] != n - n // 3:
            raise AssertionError("construction/filter result mismatch")
        if filtering["metrics"]["relation_rows_scanned"] != n:
            raise AssertionError("filter must visit each row exactly once")
        scaling.append({"n": n, "construction": build, "filter": filtering, "total": total, "delta": trace})
    cases = [("bounded_comparison", 1009 * 1013), ("old_ceiling", 10007 * 10009),
             ("search_compression", 5 * 10007 * 10009)]
    if not quick:
        cases += [("sqrt_15000", 14983 * 14999), ("sqrt_20000", 19993 * 19997),
                  ("sqrt_25000", 24979 * 24989)]
    results = []
    with tempfile.TemporaryDirectory(prefix="reason-state-benchmark-") as directory:
        naive = Path(directory) / "naive"
        subprocess.run(["rustc", "-O", str(ROOT / "benchmarks/relation_state_naive.rs"), "-o", str(naive)], check=True)
        for label, n in cases:
            naive_durations = []
            for _ in range(samples):
                started = time.perf_counter()
                completed = subprocess.run([str(naive), str(n)], text=True, capture_output=True, check=True)
                naive_durations.append(time.perf_counter() - started)
            expected = json.loads(completed.stdout)
            models = {"A": {"median_seconds": statistics.median(naive_durations), "result": expected}}
            for model in ["B", "D", *(["C-old"] if label == "bounded_comparison" else [])]:
                models[model] = measured(factorization(n, model), samples, "full" if model == "C-old" else "delta")
                answer = models[model]["result"]["fields"]
                if answer["factors"] != expected["factors"] or math.prod(answer["factors"]) != n:
                    raise AssertionError((label, model, answer, expected))
            results.append({"case": label, "input": n, "sqrt_input": math.isqrt(n), "models": models})
    old_ceiling = next(case for case in results if case["case"] == "old_ceiling")
    compressed = next(case for case in results if case["case"] == "search_compression")
    by_size = {row["n"]: row for row in scaling}
    ratio = (by_size[8000]["total"]["median_seconds"] / by_size[1000]["total"]["median_seconds"]) if 8000 in by_size else None
    acceptance = {
        "predicate_and_capture": True,
        "builder_no_full_copies": all(row["construction"]["metrics"]["builder_full_copies"] == 0 for row in scaling),
        "single_filter_exactly_n_visits": True,
        "scaling_8n_over_n_below_quadratic": ratio is None or ratio < 32,
        "old_ceiling_under_20_seconds": old_ceiling["models"]["D"]["median_seconds"] < 20,
        "old_ceiling_trace_under_10mb": old_ceiling["models"]["D"]["metrics"]["trace_bytes"] < 10_000_000 and not old_ceiling["models"]["D"]["trace_diagnostics"],
        "search_compression": compressed["models"]["D"]["result"]["fields"]["candidate_tests"] < compressed["models"]["B"]["result"]["fields"]["candidate_tests"],
        "determinism": all(case["models"]["D"]["deterministic"] for case in results),
        "staged_ceiling_under_20_seconds": all(case["models"]["D"]["median_seconds"] < 20 for case in results if case["case"].startswith("sqrt_")),
    }
    return {"schema": SCHEMA, "experiment": "SpecTest v1.3 / Experiment D", "samples": samples,
            "baseline_provenance": "C-old reconstructed from the specification; original v1.2 source fixtures were not supplied",
            "timing_scope": "native process boundary, decoding and execution; frontend lowering excluded",
            "memory_scope": "cumulative native child-process high-water RSS, not per-case peak allocation",
            "scaling_8n_over_n": ratio, "scaling": scaling, "factorization": results, "acceptance": acceptance,
            "ok": all(acceptance.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be positive")
    result = benchmark(args.samples, quick=args.quick)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    if args.summary:
        print(json.dumps({"ok": result["ok"], "acceptance": result["acceptance"],
                          "scaling_8n_over_n": result["scaling_8n_over_n"],
                          "cases": [{"case": case["case"], "seconds": case["models"]["D"]["median_seconds"],
                                     "trace_bytes": case["models"]["D"]["metrics"]["trace_bytes"],
                                     "tests_b": case["models"]["B"]["result"]["fields"]["candidate_tests"],
                                     "tests_d": case["models"]["D"]["result"]["fields"]["candidate_tests"]}
                                    for case in result["factorization"]]}, indent=2))
    else:
        print(text, end="")
    return 1 if args.check and not result["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
