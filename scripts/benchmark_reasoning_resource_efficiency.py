#!/usr/bin/env python3
"""ReasonScript Reasoning-to-Resource Efficiency Test v1.0: Model B
(numerical wheel-6 search) vs Model E (lazy / symbolic reasoning) at the
runtime-host boundary.

Spec: docs/specifications/ReasonScript_Reasoning_to_Resource_Efficiency_Test_v1_0.md
(implementation decisions: same document, section 37).

Two datasets:
  - the existing ReasonScript_SpecTest v1.3 79-case dataset (organic
    problem classes: prime, semiprime, highly_composite, ...), and
  - a synthetic 2D matrix (search space size x compression level):
    N = p1 x ... x pk x q, p1..pk small wheel-6-compatible primes, q a
    single large prime chosen so sqrt(N) lands near a target search-space
    size (1k/10k/100k/1M). k in {0,1,2,3,4,6,8,10,12}, clipped per target
    so the product stays a safe i64.

Each case runs Model B and Model E with 3 warm-up requests + 10 measured
requests (trace=off, reasoning events in `count` mode) on ONE runtime
host process reused per request (spec section 6/18/19), and writes

    <out>/comparison.csv   one row per case: RCR, POR, AER, RTER, REI, ...
    <out>/summary.json     Level 1-6 verdicts, correlations, break-even
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frontend.computation_ir import lower_program, validate_program  # noqa: E402
from frontend.computation_ir.optimizer import optimize_program  # noqa: E402
from frontend.computation_ir.rust_bridge import find_binary  # noqa: E402
from frontend.language_surface import parse  # noqa: E402
from scripts.benchmark_p0_runtime import load_dataset, pearson, request, run_host  # noqa: E402

SCHEMA = "reasonscript-reasoning-resource-efficiency/1.0"
TEMPLATES = {"B": "factorize_reasoning.rsn.template", "E": "factorize_lazy_sieve_reasoning.rsn.template"}
LIMITS = {"max_wall_time_ms": 60_000}
WARMUP = 3
SAMPLES = 10
I64_SAFE_MAX = 2**62  # generous margin under 2**63-1 (spec section 37)
# Wheel-6-compatible small primes (5 and up; 2 and 3 are handled by RU-01/02
# in both models before any candidate space or wheel-6 scan starts).
SMALL_PRIMES = [5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79]
SEARCH_SPACE_TARGETS = (1_000, 10_000, 100_000, 1_000_000)
COMPRESSION_LEVELS = (0, 1, 2, 3, 4, 6, 8, 10, 12)


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for a in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def next_prime(n: int) -> int:
    candidate = max(n, 2)
    if candidate % 2 == 0:
        candidate += 1
    while not is_prime(candidate):
        candidate += 2
    return candidate


def synthetic_cases():
    """The (search space size, compression level) matrix of spec section
    17, generated as N = product(k small primes) x q.

    The wheel-6 candidate space's upper bound is fixed once, at creation,
    to isqrt(remaining) where `remaining` is N with only 2s and 3s removed
    (RU-01/02) -- i.e. BEFORE any of p1..pk is found and divided out. So
    the search space actually scanned is sqrt(prefix * q), not sqrt(q):
    q must be chosen as roughly target**2 / prefix, not target**2, for
    sqrt(N) to land near `target` independently of k. (An earlier version
    of this generator used q ~ target**2 directly, which for k=6,
    target=1e6 produced an actual search space of ~1.27e9 instead of the
    intended 1e6 -- a real bug, not a deliberate stress case; it made
    B and E each scan ~30-40 million candidates, ~14s per run.)
    """
    for target in SEARCH_SPACE_TARGETS:
        for k in COMPRESSION_LEVELS:
            if k > len(SMALL_PRIMES):
                continue
            primes = SMALL_PRIMES[:k]
            prefix = math.prod(primes) if primes else 1
            q_floor = target * target // prefix
            if q_floor < 2:
                continue  # not enough room below target**2 for a q at this k
            q = next_prime(q_floor)
            n = prefix * q
            if n > I64_SAFE_MAX:
                continue  # spec section 37: skip combinations that would overflow i64
            yield f"synthetic_sqrt{target}_k{k}", n, f"synthetic_k{k}", target


def lower(template: str, n: int) -> dict:
    ir = optimize_program(lower_program(parse(template.replace("__N__", str(n)))))
    errors = validate_program(ir)
    if errors:
        raise ValueError(errors)
    return ir


def percentiles(values: list) -> dict:
    values = sorted(v for v in values if v is not None)
    if not values:
        return {"median": None, "p25": None, "p75": None, "min": None, "max": None}
    n = len(values)
    return {
        "median": statistics.median(values),
        "p25": values[max(0, round(0.25 * (n - 1)))],
        "p75": values[max(0, round(0.75 * (n - 1)))],
        "min": values[0],
        "max": values[-1],
    }


TRACKED_METRICS = ("runtime_execution_ns", "vm_instruction_count", "allocation_count", "allocated_bytes", "peak_live_bytes")


def measure(host, ir: dict, *, warmup: int = WARMUP, samples: int = SAMPLES) -> dict:
    """warmup + samples requests against one host binary (spec sections 6,
    18, 19); returns percentile stats for the measurement metrics and the
    deterministic counts from the last run (unchanged across runs -- see
    tests/runtime/test_candidate_space_determinism.py)."""
    payload = request(ir, mode="off", event_mode="count", limits=LIMITS)
    for _ in range(warmup):
        run_host(host, payload)
    runs = [run_host(host, payload)[0] for _ in range(samples)]
    metrics = [(run.get("metadata") or {}).get("runtime_metrics") or {} for run in runs]
    last = runs[-1]
    ok = all(run.get("ok") for run in runs)
    stats = {key: percentiles([m.get(key) for m in metrics]) for key in TRACKED_METRICS}
    m = metrics[-1]
    return {
        "ok": ok,
        "result": last.get("calculation_results", {}).get("Result") if ok else None,
        "termination_reason": (last.get("metadata") or {}).get("termination_reason"),
        "stats": stats,
        "loop_iteration_count": m.get("loop_iteration_count"),
        "hypothesis_test_count": m.get("hypothesis_test_count"),
        "candidate_generated_count": m.get("candidate_generated_count"),
        "candidate_skipped_count": m.get("candidate_skipped_count"),
        "relation_dispatch_count": m.get("relation_dispatch_count"),
        "candidate_constraint_eval_count": m.get("candidate_constraint_eval_count"),
        "branch_count": m.get("branch_count"),
        "state_transition_count": m.get("state_transition_count"),
    }


def ratio(a, b):
    return round(a / b, 6) if a is not None and b else None


def geomean(values):
    values = [v for v in values if v is not None and v > 0]
    return round(math.exp(sum(math.log(v) for v in values) / len(values)), 6) if values else None


def search_space_bucket(sqrt_n: int) -> str:
    if sqrt_n < 1_000:
        return "<1e3"
    if sqrt_n < 10_000:
        return "1e3-1e4"
    if sqrt_n < 100_000:
        return "1e4-1e5"
    if sqrt_n < 1_000_000:
        return "1e5-1e6"
    return ">=1e6"


def break_even_rcr(cases: list[dict]) -> float | None:
    """Spec section 13: the smallest RCR such that every case at or above
    it has RTER >= 1 (a continuous reasoning-favorable region from there
    up), scanning candidate thresholds in ascending RCR order."""
    ordered = sorted((c for c in cases if c["RCR"] is not None and c["RTER"] is not None), key=lambda c: c["RCR"])
    for i, case in enumerate(ordered):
        if all(later["RTER"] >= 1 for later in ordered[i:]):
            return case["RCR"]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spectest", type=Path, default=Path.home() / "development/ReasonScript_SpecTest")
    parser.add_argument("--host", type=Path, default=find_binary())
    parser.add_argument("--samples", type=int, default=SAMPLES)
    parser.add_argument("--warmup", type=int, default=WARMUP)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/reasoning_resource_efficiency")
    parser.add_argument("--quick", action="store_true", help="every 6th organic case, samples=3, warmup=1")
    args = parser.parse_args()
    if args.host is None or not args.host.is_file():
        sys.exit("runtime host not found; build ReasonRuntime first")
    templates = {model: (args.spectest / "reasonscript" / name).read_text() for model, name in TEMPLATES.items()}
    dataset = load_dataset(args.spectest)
    samples, warmup = (3, 1) if args.quick else (args.samples, args.warmup)
    if args.quick:
        dataset = dataset[::6]
    cases_to_run = [(test_id, n, cls, None) for test_id, n, cls in dataset]
    cases_to_run += [(test_id, n, cls, target) for test_id, n, cls, target in synthetic_cases()]
    args.out.mkdir(parents=True, exist_ok=True)

    rows = []
    print(f"{len(cases_to_run)} cases ({len(dataset)} organic + {len(cases_to_run) - len(dataset)} synthetic); host={args.host}")
    for test_id, n, cls, target in cases_to_run:
        b = measure(args.host, lower(templates["B"], n), samples=samples, warmup=warmup)
        e = measure(args.host, lower(templates["E"], n), samples=samples, warmup=warmup)
        if not (b["ok"] and e["ok"]):
            print(f"  {test_id:32s} SKIPPED (ok B={b['ok']} E={e['ok']}, termination B={b['termination_reason']} E={e['termination_reason']})")
            continue
        # Model B's frozen v1.1 template divides out only one power of the
        # current candidate per outer-loop check (it does not have Model
        # D/E's inner "while remaining % c == 0" loop), so for the narrow
        # edge case where remaining after small-prime removal is exactly
        # p^2 for a single wheel-6 candidate p == isqrt(remaining), B's
        # outer bound check fails before it can re-test p against the
        # shrunk remaining and it leaves remaining == p instead of 1
        # (basic_100 = 2^2*5^2 is the only such case in this dataset).
        # This is a genuine semantic difference in the pre-existing,
        # unmodified Model B reference template, not a bug in this run;
        # such cases are recorded but excluded from the aggregate
        # statistics below (spec section 5's fairness condition assumes
        # identical factor-extraction semantics, which this narrow case
        # violates through no fault of Model E).
        results_identical = b["result"] == e["result"]
        if not results_identical:
            print(f"  {test_id:32s} MISMATCH result B={b['result']} E={e['result']} (excluded from aggregate stats)")
        candidate_tests_b = b["loop_iteration_count"]
        hypothesis_tests_e = e["hypothesis_test_count"]
        rcr = ratio(candidate_tests_b, hypothesis_tests_e)
        por = ratio(b["stats"]["vm_instruction_count"]["median"], e["stats"]["vm_instruction_count"]["median"])
        aer = ratio(b["stats"]["allocation_count"]["median"], e["stats"]["allocation_count"]["median"])
        rter = ratio(b["stats"]["runtime_execution_ns"]["median"], e["stats"]["runtime_execution_ns"]["median"])
        sqrt_n = math.isqrt(n)
        row = {
            "test_id": test_id, "problem_class": cls, "N": n, "sqrt_N": sqrt_n,
            "search_space_bucket": search_space_bucket(sqrt_n), "search_space_target": target,
            "candidate_tests_B": candidate_tests_b, "hypothesis_tests_E": hypothesis_tests_e,
            "candidate_generated_E": e["candidate_generated_count"], "candidate_skipped_E": e["candidate_skipped_count"],
            "RCR": rcr,
            "vm_instr_B": b["stats"]["vm_instruction_count"]["median"], "vm_instr_E": e["stats"]["vm_instruction_count"]["median"], "POR": por,
            "alloc_B": b["stats"]["allocation_count"]["median"], "alloc_E": e["stats"]["allocation_count"]["median"], "AER": aer,
            "runtime_ns_B": b["stats"]["runtime_execution_ns"]["median"], "runtime_ns_E": e["stats"]["runtime_execution_ns"]["median"], "RTER": rter,
            "runtime_ns_B_p25": b["stats"]["runtime_execution_ns"]["p25"], "runtime_ns_B_p75": b["stats"]["runtime_execution_ns"]["p75"],
            "runtime_ns_E_p25": e["stats"]["runtime_execution_ns"]["p25"], "runtime_ns_E_p75": e["stats"]["runtime_execution_ns"]["p75"],
            "runtime_ns_B_min": b["stats"]["runtime_execution_ns"]["min"], "runtime_ns_B_max": b["stats"]["runtime_execution_ns"]["max"],
            "runtime_ns_E_min": e["stats"]["runtime_execution_ns"]["min"], "runtime_ns_E_max": e["stats"]["runtime_execution_ns"]["max"],
            "peak_memory_B": b["stats"]["peak_live_bytes"]["median"], "peak_memory_E": e["stats"]["peak_live_bytes"]["median"],
            "allocated_bytes_B": b["stats"]["allocated_bytes"]["median"], "allocated_bytes_E": e["stats"]["allocated_bytes"]["median"],
            "relation_dispatch_B": b["relation_dispatch_count"], "relation_dispatch_E": e["relation_dispatch_count"],
            "constraint_eval_E": e["candidate_constraint_eval_count"],
            "branch_B": b["branch_count"], "branch_E": e["branch_count"],
            "state_transition_B": b["state_transition_count"], "state_transition_E": e["state_transition_count"],
            "REI": geomean([por, aer, rter]),
            "termination_B": b["termination_reason"], "termination_E": e["termination_reason"],
            "results_identical": results_identical,
        }
        rows.append(row)
        print(f"  {test_id:32s} RCR={rcr:<7} POR={por:<8} AER={aer:<9} RTER={rter:<7} sqrt_N={sqrt_n}")

    with (args.out / "comparison.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    excluded = [r for r in rows if not r["results_identical"]]
    analysis_rows = [r for r in rows if r["results_identical"]]
    rter_gt_1 = [r for r in analysis_rows if r["RTER"] is not None and r["RTER"] > 1]
    compressed = [r for r in analysis_rows if r["RCR"] is not None and r["RCR"] > 1]
    level1 = [r for r in compressed if r["POR"] and r["POR"] > 1]
    level2 = [r for r in compressed if r["AER"] and r["AER"] > 1]
    # Level 4: RTER > 1 reproducible across >= 2 distinct search-space buckets for one problem class.
    by_class: dict[str, set[str]] = {}
    for r in rter_gt_1:
        by_class.setdefault(r["problem_class"], set()).add(r["search_space_bucket"])
    level4_classes = {cls: sorted(buckets) for cls, buckets in by_class.items() if len(buckets) >= 2}
    corr_por = pearson([r["RCR"] for r in analysis_rows], [r["POR"] for r in analysis_rows])
    corr_rter = pearson([r["RCR"] for r in analysis_rows], [r["RTER"] for r in analysis_rows])
    break_even = break_even_rcr(analysis_rows)
    break_even_by_bucket = {
        bucket: break_even_rcr([r for r in analysis_rows if r["search_space_bucket"] == bucket])
        for bucket in sorted({r["search_space_bucket"] for r in analysis_rows})
    }
    def med(key):
        values = [r[key] for r in analysis_rows if r[key] is not None]
        return statistics.median(values) if values else None

    summary = {
        "schema": SCHEMA, "cases_total": len(rows), "samples": samples, "warmup": warmup, "host": str(args.host),
        "excluded_result_mismatches": [r["test_id"] for r in excluded],
        "cases_analyzed": len(analysis_rows),
        "cases_RTER_gt_1": len(rter_gt_1),
        "median_RCR": med("RCR"), "median_POR": med("POR"), "median_AER": med("AER"), "median_RTER": med("RTER"),
        "correlation_RCR_POR": corr_por, "correlation_RCR_RTER": corr_rter,
        "break_even_RCR": break_even, "break_even_search_space": break_even_by_bucket,
        "levels": {
            "Level_1_compression_reduces_vm_instructions": {"pass": bool(level1), "cases": len(level1), "of_compressed": len(compressed)},
            "Level_2_compression_reduces_allocations": {"pass": bool(level2), "cases": len(level2), "of_compressed": len(compressed)},
            "Level_3_E_faster_than_B_exists": {"pass": bool(rter_gt_1), "cases": len(rter_gt_1), "of_total": len(rows)},
            "Level_4_E_faster_reproducible_across_sizes": {"pass": bool(level4_classes), "classes": level4_classes},
            "Level_5_positive_correlation": {"pass": bool(corr_rter and corr_rter >= 0.5), "pearson_r": corr_rter},
            "Level_6_break_even_identified": {"pass": break_even is not None, "break_even_RCR": break_even},
        },
        "regions": {
            "numerical_favorable_RTER_lt_1": sum(1 for r in analysis_rows if r["RTER"] is not None and r["RTER"] < 0.95),
            "break_even_RTER_approx_1": sum(1 for r in analysis_rows if r["RTER"] is not None and 0.95 <= r["RTER"] <= 1.05),
            "reasoning_favorable_RTER_gt_1": sum(1 for r in analysis_rows if r["RTER"] is not None and r["RTER"] > 1.05),
        },
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
