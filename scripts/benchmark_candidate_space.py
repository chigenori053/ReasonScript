#!/usr/bin/env python3
"""Lazy / Symbolic Candidate Space v0.1: Model D vs Model E on the
ReasonScript_SpecTest v1.3 dataset (spec sections 36-53).

Runs Model B (wheel-6), Model D (materialized sieve reasoning) and Model E
(lazy sieve reasoning, `factorize_lazy_sieve_reasoning.rsn.template`) on
ONE runtime host at the host boundary (trace=off, reasoning events in
COUNT mode for performance; trace=delta, FULL events, three runs each for
equivalence and determinism -- the same method as `benchmark_p0_runtime.py`,
whose helpers this script reuses) and writes

    <out>/results.json      per-case measurements for B, D and E
    <out>/comparison.csv    one row per case: D vs E metrics and ratios
    <out>/summary.json      Level A-H verdicts, medians, Pearson r

Ratios (spec 48-52): CMR = materialized / estimated space (E),
GER = hypothesis tests / generated candidates (E), PCR = D/E VM
instructions, ACR = D/E allocations, RTR = D/E runtime_execution_ns.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frontend.computation_ir.rust_bridge import find_binary  # noqa: E402
from scripts.benchmark_p0_runtime import load_dataset, lower, measure_model, measure_rust, pearson, ratio  # noqa: E402

SCHEMA = "reasonscript-candidate-space-profile/1.0"
TEMPLATES = {
    "B": "factorize_reasoning.rsn.template",
    "D": "factorize_sieve_reasoning.rsn.template",
    "E": "factorize_lazy_sieve_reasoning.rsn.template",
}
LIMITS = {"max_wall_time_ms": 60_000}
FOCUS_CLASSES = ("highly_composite", "mixed_factor_composite")


def hypothesis_sequence(measurement: dict) -> list[str]:
    return [event for event in measurement["event_sequence"] if event.startswith("HYPOTHESIS")]


def median(values):
    values = [value for value in values if value is not None]
    return statistics.median(values) if values else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spectest", type=Path, default=Path.home() / "development/ReasonScript_SpecTest")
    parser.add_argument("--host", type=Path, default=find_binary())
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/candidate_space_profile")
    parser.add_argument("--quick", action="store_true", help="every 6th case only")
    args = parser.parse_args()
    if args.host is None or not args.host.is_file():
        sys.exit("runtime host not found; build ReasonRuntime first")
    rust_bin = args.spectest / "rust_ref/target/release/factorize"
    templates = {model: (args.spectest / "reasonscript" / name).read_text() for model, name in TEMPLATES.items()}
    dataset = load_dataset(args.spectest)
    if args.quick:
        dataset = dataset[::6]
    args.out.mkdir(parents=True, exist_ok=True)

    cases, rows = [], []
    print(f"{len(dataset)} cases; host={args.host}")
    for test_id, n, cls in dataset:
        rust = measure_rust(rust_bin, n, args.samples) if rust_bin.is_file() else None
        models = {model: measure_model(args.host, lower(template, n), args.samples, LIMITS) for model, template in templates.items()}
        cases.append({"test_id": test_id, "input": n, "input_bits": n.bit_length(), "problem_class": cls, "rust": rust, "models": models})
        b, d, e = models["B"], models["D"], models["E"]
        mb, md, me = b["runtime_metrics"], d["runtime_metrics"], e["runtime_metrics"]
        d_tests, e_tests = md.get("hypothesis_test_count"), me.get("hypothesis_test_count")
        b_tests = mb.get("loop_iteration_count")
        # Traces are byte-budgeted; the event sequence is comparable only when
        # both traces carry every hypothesis event.
        d_seq, e_seq = hypothesis_sequence(d), hypothesis_sequence(e)
        complete = len(d_seq) == d_tests and len(e_seq) == e_tests
        row = {
            "test_id": test_id, "input": n, "input_bits": n.bit_length(), "problem_class": cls,
            "result_D": d["result"], "result_E": e["result"],
            "results_identical": d["ok"] and e["ok"] and d["result"] == e["result"],
            "hypothesis_tests_identical": d["ok"] and e["ok"] and d_tests == e_tests
                and md.get("reasoning_event_type_counts", {}).get("HYPOTHESIS_VERIFIED") == me.get("reasoning_event_type_counts", {}).get("HYPOTHESIS_VERIFIED"),
            "hypothesis_sequence_identical": (d_seq == e_seq) if complete else None,
            "hypothesis_sequence_compared": complete,
            "deterministic_E": e["deterministic"], "deterministic_D": d["deterministic"],
            "termination_D": d["termination_reason"], "termination_E": e["termination_reason"],
            "wheel6_candidate_tests": b_tests, "sieve_hypothesis_tests": d_tests, "lazy_hypothesis_tests": e_tests,
            "search_compression_ratio": ratio(b_tests, e_tests),
            "candidate_space_estimated_size": me.get("candidate_space_estimated_size"),
            "candidate_generated_count": me.get("candidate_generated_count"),
            "candidate_skipped_count": me.get("candidate_skipped_count"),
            "candidate_symbolically_excluded_count": me.get("candidate_symbolically_excluded_count"),
            "candidate_materialized_count": me.get("candidate_materialized_count"),
            "candidate_constraint_count": me.get("candidate_constraint_count"),
            "candidate_constraint_eval_count": me.get("candidate_constraint_eval_count"),
            "candidate_space_next_count": me.get("candidate_space_next_count"),
            "sieve_builder_appends": md.get("builder_appends"), "sieve_filter_rows_scanned": md.get("relation_filter_rows_scanned"),
            "lazy_filter_rows_scanned": me.get("relation_filter_rows_scanned"),
            "vm_instructions_B": mb.get("vm_instruction_count"), "vm_instructions_D": md.get("vm_instruction_count"), "vm_instructions_E": me.get("vm_instruction_count"),
            "allocations_B": mb.get("allocation_count"), "allocations_D": md.get("allocation_count"), "allocations_E": me.get("allocation_count"),
            "allocated_bytes_D": md.get("allocated_bytes"), "allocated_bytes_E": me.get("allocated_bytes"),
            "exec_ns_B": b["runtime_execution_ns"], "exec_ns_D": d["runtime_execution_ns"], "exec_ns_E": e["runtime_execution_ns"],
            "wall_ms_B": round(b["wall_time_ms"], 3), "wall_ms_D": round(d["wall_time_ms"], 3), "wall_ms_E": round(e["wall_time_ms"], 3),
            "peak_mb_D": d["peak_memory_mb"], "peak_mb_E": e["peak_memory_mb"],
            "CMR": ratio(me.get("candidate_materialized_count"), me.get("candidate_space_estimated_size")) if me.get("candidate_space_estimated_size") else 0.0,
            "GER": ratio(e_tests, me.get("candidate_generated_count")),
            "PCR": ratio(md.get("vm_instruction_count"), me.get("vm_instruction_count")),
            "ACR": ratio(md.get("allocation_count"), me.get("allocation_count")),
            "RTR": ratio(d["runtime_execution_ns"], e["runtime_execution_ns"]),
            "wall_ratio_D_over_E": ratio(d["wall_time_ms"], e["wall_time_ms"]),
            "exec_ratio_D_over_B": ratio(d["runtime_execution_ns"], b["runtime_execution_ns"]),
            "exec_ratio_E_over_B": ratio(e["runtime_execution_ns"], b["runtime_execution_ns"]),
            "wall_ratio_E_over_B": ratio(e["wall_time_ms"], b["wall_time_ms"]),
        }
        rows.append(row)
        print(f"  {test_id:28s} tests B/D/E={b_tests}/{d_tests}/{e_tests} gen={row['candidate_generated_count']} "
              f"PCR={row['PCR']} ACR={row['ACR']} RTR={row['RTR']} E/B={row['exec_ratio_E_over_B']} identical={row['results_identical']}/{row['hypothesis_sequence_identical']}")

    completed = [r for r in rows if r["termination_D"] == "completed" and r["termination_E"] == "completed"]
    focus = [r for r in completed if r["problem_class"] in FOCUS_CLASSES]
    highly = [r for r in completed if r["problem_class"] == "highly_composite"]
    hc24 = next((r for r in rows if r["test_id"] == "highly_composite_24b"), None)
    d_slower_than_b = [r for r in completed if r["exec_ratio_D_over_B"] and r["exec_ratio_D_over_B"] > 1]
    e_at_or_below_b = [r["test_id"] for r in d_slower_than_b if r["exec_ratio_E_over_B"] is not None and r["exec_ratio_E_over_B"] <= 1]
    compressed = [r for r in completed if r["search_compression_ratio"] and r["search_compression_ratio"] > 1]
    chain = [r for r in compressed if r["candidate_generated_count"] < r["wheel6_candidate_tests"]
             and r["vm_instructions_E"] < r["vm_instructions_D"] and r["allocations_E"] < r["allocations_D"] and r["exec_ns_E"] < r["exec_ns_D"]]
    corr = pearson([r["search_compression_ratio"] for r in completed], [r["RTR"] for r in completed])
    corr_e_over_b = pearson([r["search_compression_ratio"] for r in completed], [1 / r["exec_ratio_E_over_B"] if r["exec_ratio_E_over_B"] else None for r in completed])
    summary = {
        "schema": SCHEMA, "cases": len(rows), "samples": args.samples, "host": str(args.host),
        "Level_A_results_identical": {"pass": all(r["results_identical"] for r in rows), "failing": [r["test_id"] for r in rows if not r["results_identical"]]},
        "Level_B_hypothesis_sequence_identical": {
            "pass": all(r["hypothesis_tests_identical"] for r in rows) and all(r["hypothesis_sequence_identical"] for r in rows if r["hypothesis_sequence_compared"]),
            "sequence_compared_cases": sum(1 for r in rows if r["hypothesis_sequence_compared"]),
            "count_only_cases": [r["test_id"] for r in rows if not r["hypothesis_sequence_compared"]],
        },
        "Level_C_no_materialization": {
            "pass": all(r["candidate_materialized_count"] == 0 for r in completed) and all(r["lazy_filter_rows_scanned"] == 0 for r in completed),
            "max_CMR": max((r["CMR"] or 0) for r in completed), "median_GER": median([r["GER"] for r in completed]),
        },
        "Level_D_highly_composite_allocations_minus_50_percent": {"pass": bool(highly) and all(r["ACR"] and r["ACR"] >= 2 for r in highly),
                                                                  "median_ACR": median([r["ACR"] for r in highly]), "cases": len(highly)},
        "Level_E_highly_composite_24b_runtime": {"pass": bool(hc24 and hc24["RTR"] and hc24["RTR"] > 1), "RTR": hc24 and hc24["RTR"],
                                                 "exec_ns_D": hc24 and hc24["exec_ns_D"], "exec_ns_E": hc24 and hc24["exec_ns_E"]},
        "Level_F_E_at_or_below_wheel6_where_D_was_slower": {"pass": bool(e_at_or_below_b), "cases": e_at_or_below_b, "of": len(d_slower_than_b)},
        "Level_G_compression_vs_runtime_correlation": {"pass": bool(corr and corr >= 0.5), "pearson_r_compression_vs_RTR": corr,
                                                       "pearson_r_compression_vs_E_advantage_over_B": corr_e_over_b, "cases": len(completed),
                                                       "compression_ratio_distribution": {"min": min(r["search_compression_ratio"] for r in completed), "max": max(r["search_compression_ratio"] for r in completed),
                                                                                          "cases_above_1": len(compressed)}},
        "Level_H_chain_compression_to_runtime": {"pass": bool(compressed) and len(chain) == len(compressed), "cases_with_compression": len(compressed), "cases_with_full_chain": len(chain),
                                                 "failing": [r["test_id"] for r in compressed if r not in chain]},
        "determinism": {"pass": all(r["deterministic_E"] and r["deterministic_D"] for r in rows)},
        "medians": {
            "all": {k: median([r[k] for r in completed]) for k in ("PCR", "ACR", "RTR", "GER", "exec_ratio_D_over_B", "exec_ratio_E_over_B", "wall_ratio_D_over_E")},
            "focus_classes": {k: median([r[k] for r in focus]) for k in ("PCR", "ACR", "RTR", "GER", "exec_ratio_D_over_B", "exec_ratio_E_over_B")},
            "by_class": {cls: {k: median([r[k] for r in completed if r["problem_class"] == cls]) for k in ("PCR", "ACR", "RTR", "exec_ratio_D_over_B", "exec_ratio_E_over_B", "search_compression_ratio")}
                         for cls in sorted({r["problem_class"] for r in completed})},
        },
    }
    (args.out / "results.json").write_text(json.dumps({"schema": SCHEMA, "host": str(args.host), "cases": cases}, indent=1, sort_keys=True))
    with (args.out / "comparison.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
