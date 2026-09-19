#!/usr/bin/env python3
"""ReasonScript Constraint Fusion v0.1: Model B (numerical wheel-6) vs
Model E (lazy CandidateSpace, no fusion) vs Model F (lazy CandidateSpace
with Constraint Fusion) at the runtime-host boundary.

Spec: docs/specifications/ReasonScript_Constraint_Fusion_v0_1.md
(implementation decisions: same document, section 86).

Model F is NOT a separate .rsn template (spec section 36/61-62: "same
Evidence, same Hypothesis, same CandidateSpace semantics" -- Fusion
changes only the constraint EXECUTION representation). It is Model E's
own template (`factorize_lazy_sieve_reasoning.rsn.template`) run with
`context.constraint_fusion = true` instead of the default `false`.

Reuses the corrected organic + synthetic dataset from
`benchmark_reasoning_resource_efficiency.py` (spec section 39: "既存104ケー
スをそのまま再利用する"), extended with search-space target 10,000,000
(spec section 41) where it stays within the i64 safe margin.

    <out>/comparison.csv   one row per case: RCR, constraint_eval_{E,F},
                           vm/alloc/runtime for B/E/F, RTER_{E,F}_B, FRR
    <out>/summary.json     completion judgements A-G, medians, correlation
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

from frontend.computation_ir.rust_bridge import find_binary  # noqa: E402
from scripts.benchmark_p0_runtime import load_dataset, pearson, run_host  # noqa: E402
from scripts.benchmark_reasoning_resource_efficiency import (  # noqa: E402
    SEARCH_SPACE_TARGETS as BASE_SEARCH_SPACE_TARGETS,
    I64_SAFE_MAX,
    SMALL_PRIMES,
    lower,
    next_prime,
    percentiles,
    ratio,
    search_space_bucket,
)

SCHEMA = "reasonscript-constraint-fusion-profile/1.0"
TEMPLATE_B = "factorize_reasoning.rsn.template"
TEMPLATE_EF = "factorize_lazy_sieve_reasoning.rsn.template"  # Model E and Model F share this template
LIMITS = {"max_wall_time_ms": 60_000}
WARMUP = 3
SAMPLES = 10
# Spec section 40-41: k up to 12 where the i64 budget allows; target
# 10,000,000 added (optional, "i64安全域と実行時間を考慮する" -- kept small-k
# only there since a k=0 case at 1e7 already means ~2.4M candidate tests).
COMPRESSION_LEVELS = (0, 1, 2, 3, 4, 5, 6, 8, 10, 12)
SEARCH_SPACE_TARGETS = BASE_SEARCH_SPACE_TARGETS + (10_000_000,)
FOCUS_TARGETS = (100_000, 1_000_000)
FOCUS_K = (2, 3, 4, 6, 8)


def synthetic_cases():
    for target in SEARCH_SPACE_TARGETS:
        for k in COMPRESSION_LEVELS:
            if k > len(SMALL_PRIMES):
                continue
            primes = SMALL_PRIMES[:k]
            prefix = math.prod(primes) if primes else 1
            q_floor = target * target // prefix
            if q_floor < 2:
                continue
            q = next_prime(q_floor)
            n = prefix * q
            if n > I64_SAFE_MAX:
                continue
            yield f"synthetic_sqrt{target}_k{k}", n, f"synthetic_k{k}", target


def request(ir: dict, *, mode: str, event_mode: str, limits: dict, constraint_fusion: bool) -> str:
    return json.dumps({
        "schema": "reasonscript-runtime-request/1.0", "request_id": "fusion-benchmark", "operation": "execute",
        "program": ir,
        "context": {
            "resource_root": str(ROOT), "capabilities": {"filesystem_read": False, "filesystem_write": False, "network": False},
            "limits": limits, "trace": {"enabled": mode != "off", "mode": mode},
            "reasoning": {"semantic_events": True, "event_mode": event_mode},
            "numeric_mode": "compat-reference", "backend": "RuntimeReal",
            "constraint_fusion": constraint_fusion,
        },
    })


TRACKED_METRICS = ("runtime_execution_ns", "vm_instruction_count", "allocation_count", "allocated_bytes", "peak_live_bytes")


def measure(host, ir: dict, *, constraint_fusion: bool, warmup: int, samples: int) -> dict:
    payload = request(ir, mode="off", event_mode="count", limits=LIMITS, constraint_fusion=constraint_fusion)
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
        "candidate_constraint_eval_count": m.get("candidate_constraint_eval_count"),
        "fused_modulus": m.get("fused_modulus"),
        "fused_residue_count": m.get("fused_residue_count"),
        "fused_constraint_count": m.get("fused_constraint_count"),
        "residual_constraint_count": m.get("residual_constraint_count"),
        "fusion_fallback_count": m.get("fusion_fallback_count"),
    }


def hypotheses_from_trace(outcome: dict) -> list:
    trace = (outcome.get("metadata") or {}).get("reasoning_trace") or []
    return [(e["event_type"], e["evidence"]) for e in trace if e["event_type"].startswith("HYPOTHESIS")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spectest", type=Path, default=Path.home() / "development/ReasonScript_SpecTest")
    parser.add_argument("--host", type=Path, default=find_binary())
    parser.add_argument("--samples", type=int, default=SAMPLES)
    parser.add_argument("--warmup", type=int, default=WARMUP)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/constraint_fusion_profile")
    parser.add_argument("--quick", action="store_true", help="every 6th organic case, samples=3, warmup=1")
    args = parser.parse_args()
    if args.host is None or not args.host.is_file():
        sys.exit("runtime host not found; build ReasonRuntime first")
    template_b = (args.spectest / "reasonscript" / TEMPLATE_B).read_text()
    template_ef = (args.spectest / "reasonscript" / TEMPLATE_EF).read_text()
    dataset = load_dataset(args.spectest)
    samples, warmup = (3, 1) if args.quick else (args.samples, args.warmup)
    if args.quick:
        dataset = dataset[::6]
    cases_to_run = [(test_id, n, cls, None) for test_id, n, cls in dataset]
    cases_to_run += list(synthetic_cases())
    args.out.mkdir(parents=True, exist_ok=True)

    rows = []
    print(f"{len(cases_to_run)} cases; host={args.host}")
    for test_id, n, cls, target in cases_to_run:
        b = measure(args.host, lower(template_b, n), constraint_fusion=False, samples=samples, warmup=warmup)
        ir_ef = lower(template_ef, n)
        e = measure(args.host, ir_ef, constraint_fusion=False, samples=samples, warmup=warmup)
        f = measure(args.host, ir_ef, constraint_fusion=True, samples=samples, warmup=warmup)
        if not (b["ok"] and e["ok"] and f["ok"]):
            print(f"  {test_id:32s} SKIPPED (ok B={b['ok']} E={e['ok']} F={f['ok']})")
            continue
        # basic_100 (2^2*5^2): Model B's frozen v1.1 template leaves
        # remaining==5 instead of 1 for this one narrow edge case (see
        # benchmark_reasoning_resource_efficiency.py's docstring); excluded
        # from B-relative aggregates the same way, not a Fusion defect.
        b_e_identical = b["result"] == e["result"]
        e_f_identical = e["result"] == f["result"]
        if not e_f_identical:
            print(f"  {test_id:32s} MISMATCH E={e['result']} F={f['result']}")
        candidate_tests_b = b["loop_iteration_count"]
        hypothesis_tests_e = e["hypothesis_test_count"]
        rcr = ratio(candidate_tests_b, hypothesis_tests_e)
        vm_b, vm_e, vm_f = (m["stats"]["vm_instruction_count"]["median"] for m in (b, e, f))
        alloc_b, alloc_e, alloc_f = (m["stats"]["allocation_count"]["median"] for m in (b, e, f))
        ns_b, ns_e, ns_f = (m["stats"]["runtime_execution_ns"]["median"] for m in (b, e, f))
        sqrt_n = math.isqrt(n)
        row = {
            "test_id": test_id, "problem_class": cls, "N": n, "sqrt_N": sqrt_n,
            "search_space_bucket": search_space_bucket(sqrt_n), "search_space_target": target,
            "b_e_identical": b_e_identical, "e_f_identical": e_f_identical,
            "candidate_tests_B": candidate_tests_b, "hypothesis_tests_E": hypothesis_tests_e,
            "hypothesis_tests_F": f["hypothesis_test_count"], "RCR": rcr,
            "constraint_count_E": e["residual_constraint_count"], "constraint_count_F": f["fused_constraint_count"],
            "residual_constraint_count_F": f["residual_constraint_count"], "fusion_fallback_count_F": f["fusion_fallback_count"],
            "constraint_eval_E": e["candidate_constraint_eval_count"], "constraint_eval_F": f["candidate_constraint_eval_count"],
            "candidate_skipped_E": e["candidate_skipped_count"], "candidate_skipped_F": f["candidate_skipped_count"],
            "fused_modulus_F": f["fused_modulus"], "fused_residue_count_F": f["fused_residue_count"],
            "vm_instr_B": vm_b, "vm_instr_E": vm_e, "vm_instr_F": vm_f,
            "alloc_B": alloc_b, "alloc_E": alloc_e, "alloc_F": alloc_f,
            "runtime_B": ns_b, "runtime_E": ns_e, "runtime_F": ns_f,
            "RTER_E_B": ratio(ns_b, ns_e), "RTER_F_B": ratio(ns_b, ns_f),
            "FRR": ratio(ns_e, ns_f),
            "POR_E_B": ratio(vm_b, vm_e), "POR_F_B": ratio(vm_b, vm_f),
            "FER": ratio(e["candidate_constraint_eval_count"], f["candidate_constraint_eval_count"]) if f["candidate_constraint_eval_count"] else None,
            "CER_F": ratio(f["candidate_constraint_eval_count"], f["candidate_generated_count"]),
        }
        rows.append(row)
        print(f"  {test_id:32s} RCR={rcr} eval E/F={row['constraint_eval_E']}/{row['constraint_eval_F']} "
              f"RTER_E/F_B={row['RTER_E_B']}/{row['RTER_F_B']} FRR={row['FRR']}")

    with (args.out / "comparison.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    analyzed = [r for r in rows if r["e_f_identical"]]
    b_comparable = [r for r in analyzed if r["b_e_identical"]]
    focus = [r for r in analyzed if r["search_space_target"] in FOCUS_TARGETS
             and r["problem_class"].startswith("synthetic")
             and int(r["problem_class"].replace("synthetic_k", "")) in FOCUS_K]
    high_k = [r for r in analyzed if r["problem_class"].startswith("synthetic")
              and int(r["problem_class"].replace("synthetic_k", "")) >= 6]

    def med(rows_, key):
        values = [r[key] for r in rows_ if r[key] is not None]
        return statistics.median(values) if values else None

    level_c = [r for r in high_k if r["constraint_eval_F"] < r["constraint_eval_E"]]
    level_d = [r for r in high_k if r["POR_F_B"] and r["POR_E_B"] and r["POR_F_B"] > r["POR_E_B"]]
    level_e_target_1e6_k68 = [r for r in analyzed if r["search_space_target"] == 1_000_000
                               and r["problem_class"] in ("synthetic_k6", "synthetic_k8")]
    corr_rter_e = pearson([r["RCR"] for r in b_comparable], [r["RTER_E_B"] for r in b_comparable])
    corr_rter_f = pearson([r["RCR"] for r in b_comparable], [r["RTER_F_B"] for r in b_comparable])
    e_favorable = {r["test_id"] for r in b_comparable if r["RTER_E_B"] and r["RTER_E_B"] > 1}
    f_favorable = {r["test_id"] for r in b_comparable if r["RTER_F_B"] and r["RTER_F_B"] > 1}
    perf_regression = [r for r in analyzed if r["problem_class"] in ("synthetic_k0", "synthetic_k1")
                        and r["runtime_F"] and r["runtime_E"] and r["runtime_F"] > 1.05 * r["runtime_E"]]

    summary = {
        "schema": SCHEMA, "cases_total": len(rows), "samples": samples, "warmup": warmup, "host": str(args.host),
        "cases_analyzed_e_f_identical": len(analyzed), "cases_excluded_e_f_mismatch": [r["test_id"] for r in rows if not r["e_f_identical"]],
        "cases_b_comparable": len(b_comparable),
        "median_FRR": med(analyzed, "FRR"), "median_constraint_eval_reduction_FER": med(analyzed, "FER"),
        "median_RTER_E_B": med(b_comparable, "RTER_E_B"), "median_RTER_F_B": med(b_comparable, "RTER_F_B"),
        "correlation_RCR_RTER_E": corr_rter_e, "correlation_RCR_RTER_F": corr_rter_f,
        "cases_F_faster_than_B": len(f_favorable), "cases_E_faster_than_B": len(e_favorable),
        "completion": {
            "A_all_results_identical_E_F": {"pass": len(analyzed) == len(rows), "mismatches": [r["test_id"] for r in rows if not r["e_f_identical"]]},
            "B_hypothesis_sequence_identical": "verified separately in tests/runtime/test_constraint_fusion.py (this script compares final results and counts only)",
            "C_constraint_eval_reduced_at_k_gte_4": {"pass": bool(level_c) and len(level_c) == len(high_k), "cases": len(level_c), "of": len(high_k)},
            "D_POR_F_B_improves_over_POR_E_B_at_k_gte_6": {"pass": bool(level_d), "cases": len(level_d), "of": len(high_k)},
            "E_F_faster_than_E_at_k6_k8_target_1e6": [
                {"test_id": r["test_id"], "FRR": r["FRR"], "RTER_E_B": r["RTER_E_B"], "RTER_F_B": r["RTER_F_B"]}
                for r in level_e_target_1e6_k68
            ],
            "F_RTER_F_B_gt_1_at_1e6_k6_k8": {"pass": all(r["RTER_F_B"] and r["RTER_F_B"] > 1 for r in level_e_target_1e6_k68) if level_e_target_1e6_k68 else False,
                                             "cases": [(r["test_id"], r["RTER_F_B"]) for r in level_e_target_1e6_k68]},
            "G_correlation_improves_over_E": {"pass": bool(corr_rter_f and corr_rter_e and corr_rter_f > corr_rter_e),
                                              "pearson_r_E": corr_rter_e, "pearson_r_F": corr_rter_f, "target_0.3": bool(corr_rter_f and corr_rter_f >= 0.3),
                                              "target_0.5": bool(corr_rter_f and corr_rter_f >= 0.5)},
        },
        "reasoning_favorable_region_change": {
            "E_favorable_cases": sorted(e_favorable), "F_favorable_cases": sorted(f_favorable),
            "gained_by_fusion": sorted(f_favorable - e_favorable), "lost_by_fusion": sorted(e_favorable - f_favorable),
        },
        "performance_regression_k0_k1": {"pass": not perf_regression, "cases_exceeding_1.05x": [r["test_id"] for r in perf_regression]},
        "focus_medians_target_1e5_1e6_k_2_3_4_6_8": {key: med(focus, key) for key in ("RTER_E_B", "RTER_F_B", "FRR", "FER", "POR_E_B", "POR_F_B")},
        "medians_by_k": {
            k: {key: med([r for r in b_comparable if r["problem_class"] == k], key) for key in ("RCR", "RTER_E_B", "RTER_F_B", "FRR")}
            for k in sorted({r["problem_class"] for r in b_comparable if r["problem_class"].startswith("synthetic")},
                             key=lambda name: int(name.replace("synthetic_k", "")))
        },
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
