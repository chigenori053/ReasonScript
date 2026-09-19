#!/usr/bin/env python3
"""ReasonScript Adaptive / Cost-Aware Constraint Fusion v0.1: Model B
(numerical wheel-6) vs Model E (Fusion off) vs Model F (Fusion always) vs
Model G (Fusion adaptive) at the runtime-host boundary.

Spec: docs/specifications/ReasonScript_Adaptive_Cost_Aware_Constraint_Fusion_v0_1.md
(implementation decisions: same document, section 133).

Model G is Model E's own template run with `context.constraint_fusion =
"adaptive"` -- no new .rsn template or surface syntax (spec section 9-10,
61-62).

Reuses the exact 117-case dataset (79 organic + synthetic 2D matrix) from
`benchmark_constraint_fusion.py` (spec section 48).

    <out>/comparison.csv   one row per case: RCR, runtime_{B,E,F,G},
                           RTER_{E,F,G}_B, FRR_F_E, GRR (E/G), GRF (F/G),
                           fusion_candidate/selected/rejected_cost_G, ...
    <out>/summary.json     completion judgements 1-9, oracle efficiency,
                           correlation, favorable-region comparison
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
from scripts.benchmark_constraint_fusion import synthetic_cases  # noqa: E402
from scripts.benchmark_p0_runtime import load_dataset, pearson, run_host  # noqa: E402
from scripts.benchmark_reasoning_resource_efficiency import lower, percentiles, ratio, search_space_bucket  # noqa: E402

SCHEMA = "reasonscript-adaptive-fusion-profile/1.0"
TEMPLATE_B = "factorize_reasoning.rsn.template"
TEMPLATE_EFG = "factorize_lazy_sieve_reasoning.rsn.template"  # E, F and G share this template
LIMITS = {"max_wall_time_ms": 60_000}
WARMUP = 3
SAMPLES = 10
# Constraint Fusion v0.1's own worst regressions (spec sections 56, 104):
# fixed regression fixtures, checked individually in the summary.
REGRESSION_FIXTURES = ("synthetic_sqrt1000000_k6", "synthetic_sqrt1000000_k8", "highly_composite_24b")
POSITIVE_FIXTURE_PREFIX = "synthetic_sqrt10000000_"

TRACKED_METRICS = ("runtime_execution_ns", "vm_instruction_count", "allocation_count", "allocated_bytes", "peak_live_bytes")


def request(ir: dict, *, mode: str, event_mode: str, limits: dict, constraint_fusion: str) -> str:
    return json.dumps({
        "schema": "reasonscript-runtime-request/1.0", "request_id": "adaptive-fusion-benchmark", "operation": "execute",
        "program": ir,
        "context": {
            "resource_root": str(ROOT), "capabilities": {"filesystem_read": False, "filesystem_write": False, "network": False},
            "limits": limits, "trace": {"enabled": mode != "off", "mode": mode},
            "reasoning": {"semantic_events": True, "event_mode": event_mode},
            "numeric_mode": "compat-reference", "backend": "RuntimeReal",
            "constraint_fusion": constraint_fusion,
        },
    })


def measure(host, ir: dict, *, policy: str, warmup: int, samples: int) -> dict:
    payload = request(ir, mode="off", event_mode="count", limits=LIMITS, constraint_fusion=policy)
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
        "stats": stats,
        "loop_iteration_count": m.get("loop_iteration_count"),
        "hypothesis_test_count": m.get("hypothesis_test_count"),
        "candidate_constraint_eval_count": m.get("candidate_constraint_eval_count"),
        "fused_constraint_count": m.get("fused_constraint_count"),
        "residual_constraint_count": m.get("residual_constraint_count"),
        "fusion_candidate_count": m.get("fusion_candidate_count"),
        "fusion_selected_count": m.get("fusion_selected_count"),
        "fusion_rejected_cost_count": m.get("fusion_rejected_cost_count"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spectest", type=Path, default=Path.home() / "development/ReasonScript_SpecTest")
    parser.add_argument("--host", type=Path, default=find_binary())
    parser.add_argument("--samples", type=int, default=SAMPLES)
    parser.add_argument("--warmup", type=int, default=WARMUP)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/adaptive_fusion_profile")
    parser.add_argument("--quick", action="store_true", help="every 6th organic case, samples=3, warmup=1")
    args = parser.parse_args()
    if args.host is None or not args.host.is_file():
        sys.exit("runtime host not found; build ReasonRuntime first")
    template_b = (args.spectest / "reasonscript" / TEMPLATE_B).read_text()
    template_efg = (args.spectest / "reasonscript" / TEMPLATE_EFG).read_text()
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
        b = measure(args.host, lower(template_b, n), policy="off", samples=samples, warmup=warmup)
        ir_efg = lower(template_efg, n)
        e = measure(args.host, ir_efg, policy="off", samples=samples, warmup=warmup)
        f = measure(args.host, ir_efg, policy="always", samples=samples, warmup=warmup)
        g = measure(args.host, ir_efg, policy="adaptive", samples=samples, warmup=warmup)
        if not (b["ok"] and e["ok"] and f["ok"] and g["ok"]):
            print(f"  {test_id:32s} SKIPPED (ok B={b['ok']} E={e['ok']} F={f['ok']} G={g['ok']})")
            continue
        results_identical = e["result"] == f["result"] == g["result"]
        # basic_100: see benchmark_reasoning_resource_efficiency.py's docstring.
        b_comparable = b["result"] == e["result"]
        if not results_identical:
            print(f"  {test_id:32s} MISMATCH E={e['result']} F={f['result']} G={g['result']}")
        candidate_tests_b = b["loop_iteration_count"]
        rcr = ratio(candidate_tests_b, e["hypothesis_test_count"])
        ns_b, ns_e, ns_f, ns_g = (m["stats"]["runtime_execution_ns"]["median"] for m in (b, e, f, g))
        sqrt_n = math.isqrt(n)
        row = {
            "test_id": test_id, "problem_class": cls, "N": n, "sqrt_N": sqrt_n,
            "search_space_bucket": search_space_bucket(sqrt_n), "search_space_target": target,
            "results_identical": results_identical, "b_comparable": b_comparable,
            "RCR": rcr,
            "runtime_B": ns_b, "runtime_E": ns_e, "runtime_F": ns_f, "runtime_G": ns_g,
            "RTER_E_B": ratio(ns_b, ns_e), "RTER_F_B": ratio(ns_b, ns_f), "RTER_G_B": ratio(ns_b, ns_g),
            "FRR_F_E": ratio(ns_e, ns_f),
            "GRR": ratio(ns_e, ns_g),  # E/G: G faster than E when > 1
            "GRF": ratio(ns_f, ns_g),  # F/G: G faster than F when > 1
            "constraint_eval_E": e["candidate_constraint_eval_count"],
            "constraint_eval_F": f["candidate_constraint_eval_count"],
            "constraint_eval_G": g["candidate_constraint_eval_count"],
            "fusion_candidate_G": g["fusion_candidate_count"],
            "fusion_selected_G": g["fusion_selected_count"],
            "fusion_rejected_cost_G": g["fusion_rejected_cost_count"],
            "fused_constraint_F": f["fused_constraint_count"], "fused_constraint_G": g["fused_constraint_count"],
            "best_E_F_runtime": min(v for v in (ns_e, ns_f) if v is not None),
            "oracle_efficiency": ratio(min(v for v in (ns_e, ns_f) if v is not None), ns_g),
        }
        rows.append(row)
        print(f"  {test_id:32s} RCR={rcr} RTER E/F/G_B={row['RTER_E_B']}/{row['RTER_F_B']}/{row['RTER_G_B']} "
              f"GRR={row['GRR']} GRF={row['GRF']} fusion_G sel/rej={row['fusion_selected_G']}/{row['fusion_rejected_cost_G']}")

    with (args.out / "comparison.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    analyzed = [r for r in rows if r["results_identical"]]
    b_comparable = [r for r in analyzed if r["b_comparable"]]

    def med(rows_, key):
        values = [r[key] for r in rows_ if r[key] is not None]
        return statistics.median(values) if values else None

    e_favorable = {r["test_id"] for r in b_comparable if r["RTER_E_B"] and r["RTER_E_B"] > 1}
    f_favorable = {r["test_id"] for r in b_comparable if r["RTER_F_B"] and r["RTER_F_B"] > 1}
    g_favorable = {r["test_id"] for r in b_comparable if r["RTER_G_B"] and r["RTER_G_B"] > 1}
    corr_e = pearson([r["RCR"] for r in b_comparable], [r["RTER_E_B"] for r in b_comparable])
    corr_f = pearson([r["RCR"] for r in b_comparable], [r["RTER_F_B"] for r in b_comparable])
    corr_g = pearson([r["RCR"] for r in b_comparable], [r["RTER_G_B"] for r in b_comparable])

    by_id = {r["test_id"]: r for r in analyzed}
    regression_recovery = []
    for fixture in REGRESSION_FIXTURES:
        r = by_id.get(fixture)
        if r is None:
            continue
        regression_recovery.append({"test_id": fixture, "runtime_E": r["runtime_E"], "runtime_F": r["runtime_F"],
                                     "runtime_G": r["runtime_G"], "G_lt_F": r["runtime_G"] < r["runtime_F"],
                                     "worst_case_was_F_2x_E": r["runtime_F"] > 2 * r["runtime_E"]})
    worst_case_cases = [c for c in regression_recovery if c["worst_case_was_F_2x_E"]]

    positive_fixtures = [r for r in analyzed if r["test_id"].startswith(POSITIVE_FIXTURE_PREFIX) and r["fusion_selected_G"]]

    k0_k1 = [r for r in analyzed if r["problem_class"] in ("synthetic_k0", "synthetic_k1")]
    k0_k1_regression = [r for r in k0_k1 if r["runtime_G"] and r["runtime_E"] and r["runtime_G"] > 1.05 * r["runtime_E"]]

    protected_e = [r for r in b_comparable if r["runtime_G"] and r["runtime_E"] and r["runtime_G"] <= 1.10 * r["runtime_E"]]

    summary = {
        "schema": SCHEMA, "cases_total": len(rows), "samples": samples, "warmup": warmup, "host": str(args.host),
        "results_identical_E_F_G": len(analyzed) == len(rows),
        "cases_analyzed": len(analyzed), "cases_b_comparable": len(b_comparable),
        "cases_excluded_mismatch": [r["test_id"] for r in rows if not r["results_identical"]],
        "median_runtime_E": med(analyzed, "runtime_E"), "median_runtime_F": med(analyzed, "runtime_F"), "median_runtime_G": med(analyzed, "runtime_G"),
        "median_GRR_E_over_G": med(b_comparable, "GRR"), "median_GRF_F_over_G": med(b_comparable, "GRF"),
        "E_favorable_cases": len(e_favorable), "F_favorable_cases": len(f_favorable), "G_favorable_cases": len(g_favorable),
        "fusion_selected_total": sum(r["fusion_selected_G"] or 0 for r in analyzed),
        "fusion_rejected_cost_total": sum(r["fusion_rejected_cost_G"] or 0 for r in analyzed),
        "oracle_efficiency_median": med(b_comparable, "oracle_efficiency"),
        "correlation_RCR_RTER_E": corr_e, "correlation_RCR_RTER_F": corr_f, "correlation_RCR_RTER_G": corr_g,
        "completion_judgements": {
            "1_semantic_equivalence": {"pass": len(analyzed) == len(rows), "mandatory": True},
            "2_worst_case_regression_recovery": {
                "pass": bool(worst_case_cases) and all(c["G_lt_F"] for c in worst_case_cases),
                "mandatory": True, "fixtures": regression_recovery,
            },
            "3_model_e_protection_95pct_within_1.10x": {
                "pass": len(protected_e) >= 0.95 * len(b_comparable) if b_comparable else False,
                "target": True, "fraction": ratio(len(protected_e), len(b_comparable)),
            },
            "4_fusion_opportunity_utilized": {"pass": any(r["fusion_selected_G"] for r in analyzed), "mandatory": True},
            "5_reasoning_favorable_region_g_gte_e": {"pass": len(g_favorable) >= len(e_favorable), "important": True,
                                                     "G_favorable": len(g_favorable), "E_favorable": len(e_favorable)},
            "6_reasoning_favorable_region_g_gt_e": {"pass": len(g_favorable) > len(e_favorable), "target": True},
            "7_oracle_efficiency_median_gte_0.9": {"pass": (med(b_comparable, "oracle_efficiency") or 0) >= 0.9, "target": True},
            "8_correlation_improves_over_f": {"pass": bool(corr_g is not None and corr_f is not None and corr_g > corr_f),
                                              "mandatory_target": True, "r_F": corr_f, "r_G": corr_g},
            "9_adaptive_overhead_not_dominant_k0_k1": {"pass": not k0_k1_regression, "target": True,
                                                       "cases_exceeding_1.05x": [r["test_id"] for r in k0_k1_regression]},
        },
        "positive_fixture_fusion_selected": {"pass": bool(positive_fixtures), "cases": [r["test_id"] for r in positive_fixtures]},
        "reasoning_favorable_region_vs_e": {
            "gained_by_adaptive": sorted(g_favorable - e_favorable), "lost_by_adaptive": sorted(e_favorable - g_favorable),
        },
        "reasoning_favorable_region_vs_f": {
            "recovered_from_f_regression": sorted(g_favorable - f_favorable), "still_lost_vs_f": sorted(f_favorable - g_favorable),
        },
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
