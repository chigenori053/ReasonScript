#!/usr/bin/env python3
"""Lightweight RUS runtime optimization benchmark (host boundary, trace off).

Compares runtime host binaries built from different commits (first `--binary`
is the baseline, the last one the optimized build; intermediates are reported
too), interleaving them sample by sample. Timing is `runtime_execution_ns`
(the `run_calculations` boundary, identical for every binary) against
`executable_reason_units=full`. Before any number is trusted it checks that the
optimized build is semantically identical to the baseline (whole response,
minus timing) for N = 2..89, the golden cases, and the benchmark corpus, and
that its hashes are stable across three runs.

    scripts/benchmark_reasoning_state.py --binary R0=path/r0-host --binary R4=path/r4-host \
        --baseline-commit <sha> [--profile R0=path/r0-profile --profile R4=path/r4-profile]

A formal evaluation additionally needs `working_tree_dirty == false`.
"""

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
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frontend.computation_ir import lower_program
from frontend.computation_ir.rust_bridge import find_binary
from frontend.language_surface import parse

GOLDEN_DIR = ROOT / "computation_ir_tests/golden_reasoning_state"
TEMPLATE = (GOLDEN_DIR / "factorize.rsn.template").read_text()
GOLDEN_CASES = [case["n"] for case in json.loads((GOLDEN_DIR / "golden.json").read_text())["cases"]]
DEFAULT_OUT = ROOT / "artifacts/reasoning_state_optimization"
CASES = (77, 997, 10007, 30030, 10403)  # semiprime, primes, highly composite, larger semiprime
EQUIVALENCE_CASES = sorted({*range(2, 90), *GOLDEN_CASES, *CASES})
CONFIGS = {
    "normal": {"executable_reason_units": "off"},
    "ru_full": {"executable_reason_units": "full"},
    "lightweight_rus": {"executable_reason_units": "full", "reasoning_state": "lightweight"},
    "state_causality": {"executable_reason_units": "full", "state_causality": "full"},
    "state_causality_native_causal": {
        "executable_reason_units": "full",
        "state_causality": "full",
        "causal_evaluation": "counterfactual",
        "causal_observation_source": "native",
    },
}
# (PASS limit, PARTIAL limit) relative to executable_reason_units=full
LIMITS = {"lightweight_rus": (0.10, 0.15), "state_causality": (0.20, 0.30)}
HASHES = {
    "reasoning_state_hash": ("reasoning_state", "hash"),
    "initial_hash": ("reasoning_state", "initial_hash"),
    "state_transition_hash": ("state_causality", "hashes", "state_transition_hash"),
    "causal_observation_hash": ("causal_bridge", "observation_hash"),
    "causal_relation_hash": ("causal_trace", "hashes", "causal_relation_hash"),
}
COMPONENTS = {
    "normal_runtime_ns": ("causal_trace", "metrics", "normal_runtime_ns"),
    "reasoning_state_runtime_ns": ("reasoning_state", "metrics", "reasoning_state_runtime_ns"),
    "state_causality_runtime_ns": ("state_causality", "metrics", "state_causality_runtime_ns"),
    "causal_bridge_runtime_ns": ("causal_bridge", "metrics", "causal_bridge_runtime_ns"),
    "causal_evaluation_ns": ("causal_trace", "metrics", "causal_evaluation_ns"),
    "state_transition_materialization_ns": ("state_causality", "metrics", "state_transition_materialization_ns"),
    "provenance_materialization_ns": ("state_causality", "metrics", "provenance_materialization_ns"),
    "transition_hash_ns": ("state_causality", "metrics", "transition_hash_ns"),
    "state_hash_ns": ("reasoning_state", "metrics", "state_hash_ns"),
}

_programs: dict[int, dict] = {}


def program(n: int) -> dict:
    if n not in _programs:
        _programs[n] = lower_program(parse(TEMPLATE.replace("__N__", str(n))))
    return _programs[n]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()


def run(binary: Path, n: int, context: dict) -> dict:
    request = {
        "schema": "reasonscript-runtime-request/1.0",
        "request_id": "reasoning-state-benchmark",
        "operation": "execute",
        "program": program(n),
        "context": {
            "resource_root": ".",
            "capabilities": {},
            "limits": {"max_loop_iterations": 1_000_000},
            "trace": {"enabled": False},
            "numeric_mode": "compat-reference",
            "benchmark_metrics": True,
            **context,
        },
    }
    completed = subprocess.run([str(binary)], input=json.dumps(request), text=True, capture_output=True)
    payload = json.loads(completed.stdout)
    assert payload["ok"], payload
    return payload


def pick(payload: dict, path: tuple[str, ...]):
    value = payload["metadata"]
    for key in path:
        value = value[key]
    return value


def without_timing(value):
    """The response minus wall-clock fields (`*_ns`, cost ratios)."""
    if isinstance(value, dict):
        return {
            key: without_timing(item)
            for key, item in value.items()
            if not key.endswith("_ns") and key != "counterfactual_cost_ratio"
        }
    if isinstance(value, list):
        return [without_timing(item) for item in value]
    return value


def equivalence(baseline: Path, optimized: Path) -> dict:
    """Whole-response identity (dict and key-order-sensitive text) plus hashes."""
    context = CONFIGS["state_causality_native_causal"]
    mismatches, checked = [], 0
    hash_matches = {name: 0 for name in HASHES}
    for n in EQUIVALENCE_CASES:
        before, after = run(baseline, n, context), run(optimized, n, context)
        left, right = without_timing(before), without_timing(after)
        same = left == right and json.dumps(left) == json.dumps(right)
        checked += 1
        if not same:
            mismatches.append(n)
        for name, path in HASHES.items():
            hash_matches[name] += pick(before, path) == pick(after, path)
    return {
        "cases": checked,
        "identical_responses": checked - len(mismatches),
        "mismatched_n": mismatches[:10],
        "hash_matches": hash_matches,
        "all_hashes_equal": all(count == checked for count in hash_matches.values()),
        "semantic_equivalence": not mismatches,
    }


def determinism(binary: Path) -> dict:
    context = CONFIGS["state_causality_native_causal"]
    runs = [{name: pick(run(binary, n, context), path) for name, path in HASHES.items()} for n in (84, 10007) for _ in range(3)]
    stable = all(runs[i] == runs[3 * (i // 3)] for i in range(len(runs)))
    return {"runs_per_case": 3, "cases": [84, 10007], "stable": stable}


def measure(binaries: dict[str, Path], warmup: int, samples: int) -> dict:
    """runtime_execution_ns medians, interleaving binaries sample by sample."""
    result: dict = {}
    for n in CASES:
        for config, context in CONFIGS.items():
            collected = {label: [] for label in binaries}
            components = {label: [] for label in binaries}
            for sample in range(warmup + samples):
                for label, binary in binaries.items():
                    payload = run(binary, n, context)
                    if sample >= warmup:
                        collected[label].append(payload["metadata"]["runtime_metrics"]["runtime_execution_ns"])
                        if config == "state_causality_native_causal":
                            components[label].append(payload)
            for label in binaries:
                entry = result.setdefault(label, {}).setdefault(n, {})
                entry[config] = int(statistics.median(collected[label]))
                if components[label]:
                    entry["components_ns"] = {
                        name: int(statistics.median(pick(p, path) for p in components[label]))
                        for name, path in COMPONENTS.items()
                        if all(_has(p, path) for p in components[label])
                    }
                    last = components[label][-1]
                    entry["transitions"] = pick(last, ("state_causality", "metrics", "state_transition_count"))
                    entry["relations"] = pick(last, ("state_causality", "metrics", "state_causal_relation_count"))
    return result


def _has(payload: dict, path: tuple[str, ...]) -> bool:
    value = payload["metadata"]
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return False
        value = value[key]
    return True


def overheads(timings: dict) -> dict:
    per_case = {
        n: {name: timings[n][name] / timings[n]["ru_full"] - 1 for name in LIMITS} for n in CASES
    }
    totals = {config: sum(timings[n][config] for n in CASES) for config in CONFIGS}
    return {
        "per_case": per_case,
        "aggregate": {name: totals[name] / totals["ru_full"] - 1 for name in LIMITS},
        "median": {name: statistics.median(per_case[n][name] for n in CASES) for name in LIMITS},
        "total_runtime_execution_ns": totals,
    }


def verdict(name: str, value: float) -> str:
    passing, partial = LIMITS[name]
    return "PASS" if value <= passing else "INTERMEDIATE" if value <= partial else "HOLD"


def in_process(profiles: dict[str, Path], iterations: int) -> dict:
    """Allocation counts and response-phase cost from the in-process harness."""
    result: dict = {}
    with tempfile.TemporaryDirectory() as directory:
        for label, binary in profiles.items():
            for n in CASES:
                path = Path(directory) / f"program-{n}.json"
                path.write_text(json.dumps(program(n)))
                for config in ("ru_full", "lightweight", "causality"):
                    completed = subprocess.run(
                        [str(binary), str(path), config, str(iterations)], text=True, capture_output=True, check=True
                    )
                    result.setdefault(label, {}).setdefault(n, {})[config] = json.loads(completed.stdout)
    return result


def end_to_end(profile: dict, labels: list[str]) -> dict:
    """run + response-construction time, so moved work is not mistaken for saved work."""
    if not profile:
        return {}
    totals = {
        label: {config: sum(profile[label][n][config]["run_ns"] + profile[label][n][config]["materialize_ns"] for n in CASES) for config in ("ru_full", "lightweight", "causality")}
        for label in profile
    }
    first, last = labels[0], labels[-1]
    return {
        "total_ns": totals,
        "optimized_over_baseline": {config: totals[last][config] / totals[first][config] for config in totals[first]},
        "run_ns_optimized_over_baseline": {
            config: sum(profile[last][n][config]["run_ns"] for n in CASES) / sum(profile[first][n][config]["run_ns"] for n in CASES)
            for config in totals[first]
        },
        "materialize_ns_optimized_over_baseline": {
            config: sum(profile[last][n][config]["materialize_ns"] for n in CASES) / sum(profile[first][n][config]["materialize_ns"] for n in CASES)
            for config in totals[first]
        },
    }


def nice_ceiling(value: float) -> float:
    """Smallest 1/2/2.5/5/10 x 10^k at or above `value`, for round axis ticks."""
    magnitude = 10 ** math.floor(math.log10(value))
    return next(step * magnitude for step in (1, 2, 2.5, 5, 10) if value <= step * magnitude)


def svg_bars(path: Path, title: str, categories: list[str], series: dict[str, list[float]], unit: str, line: float | None = None) -> None:
    width, height, left, bottom, top = 720, 360, 60, 50, 40
    peak = nice_ceiling(max([*(v for values in series.values() for v in values), line or 0, 1e-9]) * 1.05)
    colors = ["#8a94a6", "#2f6fdd", "#1f9d6b", "#d98324"]
    group = (width - left - 20) / len(categories)
    bar = group / (len(series) + 1)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" font-family="sans-serif" font-size="11">',
           f'<text x="{left}" y="22" font-size="14" font-weight="bold">{title}</text>']
    plot = height - bottom - top
    scale = lambda v: height - bottom - v / peak * plot  # noqa: E731
    for tick in range(5):
        value = peak * tick / 4
        out.append(f'<line x1="{left}" x2="{width - 20}" y1="{scale(value):.1f}" y2="{scale(value):.1f}" stroke="#ddd"/>'
                   f'<text x="{left - 6}" y="{scale(value) + 4:.1f}" text-anchor="end">{value:.3g}{unit}</text>')
    for i, category in enumerate(categories):
        for j, (label, values) in enumerate(series.items()):
            x = left + i * group + (j + 0.5) * bar
            out.append(f'<rect x="{x:.1f}" y="{scale(values[i]):.1f}" width="{bar * 0.9:.1f}" height="{height - bottom - scale(values[i]):.1f}" fill="{colors[j % 4]}"/>')
        out.append(f'<text x="{left + (i + 0.5) * group:.1f}" y="{height - bottom + 16}" text-anchor="middle">{category}</text>')
    if line is not None:
        out.append(f'<line x1="{left}" x2="{width - 20}" y1="{scale(line):.1f}" y2="{scale(line):.1f}" stroke="#c0392b" stroke-dasharray="5 3"/>'
                   f'<text x="{width - 22}" y="{scale(line) - 4:.1f}" text-anchor="end" fill="#c0392b">target {line:g}{unit}</text>')
    for j, label in enumerate(series):
        out.append(f'<rect x="{left + j * 90}" y="{height - 18}" width="10" height="10" fill="{colors[j % 4]}"/><text x="{left + j * 90 + 14}" y="{height - 9}">{label}</text>')
    path.write_text("\n".join([*out, "</svg>"]) + "\n")


def svg_scatter(path: Path, title: str, xlabel: str, ylabel: str, series: dict[str, list[tuple[float, float]]]) -> None:
    width, height, left, bottom, top = 720, 360, 70, 50, 40
    xs = [x for points in series.values() for x, _ in points] or [1]
    ys = [y for points in series.values() for _, y in points] or [1]
    x_max, y_max = max(xs) * 1.1 or 1, max(ys) * 1.1 or 1
    colors = ["#8a94a6", "#2f6fdd", "#1f9d6b", "#d98324"]
    sx = lambda x: left + x / x_max * (width - left - 20)  # noqa: E731
    sy = lambda y: height - bottom - y / y_max * (height - bottom - top)  # noqa: E731
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" font-family="sans-serif" font-size="11">',
           f'<text x="{left}" y="22" font-size="14" font-weight="bold">{title}</text>',
           f'<line x1="{left}" x2="{width - 20}" y1="{height - bottom}" y2="{height - bottom}" stroke="#555"/><line x1="{left}" x2="{left}" y1="{top}" y2="{height - bottom}" stroke="#555"/>',
           f'<text x="{(left + width) / 2:.0f}" y="{height - 22}" text-anchor="middle">{xlabel} (max {x_max / 1.1:.4g})</text>',
           f'<text x="14" y="{(top + height) / 2:.0f}" transform="rotate(-90 14 {(top + height) / 2:.0f})" text-anchor="middle">{ylabel} (max {y_max / 1.1:.4g})</text>']
    for j, (label, points) in enumerate(series.items()):
        out.extend(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="4" fill="{colors[j % 4]}"/>' for x, y in points)
        out.append(f'<rect x="{left + j * 90}" y="{height - 18}" width="10" height="10" fill="{colors[j % 4]}"/><text x="{left + j * 90 + 14}" y="{height - 9}">{label}</text>')
    path.write_text("\n".join([*out, "</svg>"]) + "\n")


def write_artifacts(out: Path, summary: dict, timings: dict, labels: list[str], profile: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    before, after = labels[0], labels[-1]
    tag = lambda label: label.lower()  # noqa: E731
    columns = ["N", "transitions", "relations", "runtime_ru_full"]
    for label in (before, after):
        columns += [f"runtime_{tag(label)}_rus", f"runtime_{tag(label)}_causality"]
    columns += ["rus_overhead_before", "rus_overhead_after", "causal_overhead_before", "causal_overhead_after"]
    with (out / "comparison.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for n in CASES:
            b, a = timings[before][n], timings[after][n]
            writer.writerow([
                n, a["transitions"], a["relations"], a["ru_full"],
                b["lightweight_rus"], b["state_causality"], a["lightweight_rus"], a["state_causality"],
                f"{b['lightweight_rus'] / b['ru_full'] - 1:.4f}", f"{a['lightweight_rus'] / a['ru_full'] - 1:.4f}",
                f"{b['state_causality'] / b['ru_full'] - 1:.4f}", f"{a['state_causality'] / a['ru_full'] - 1:.4f}",
            ])
    names = [str(n) for n in CASES]
    pct = lambda label, config: [100 * (timings[label][n][config] / timings[label][n]["ru_full"] - 1) for n in CASES]  # noqa: E731
    svg_bars(out / "graph_a_rus_overhead.svg", "Lightweight RUS overhead vs RU full", names, {before: pct(before, "lightweight_rus"), after: pct(after, "lightweight_rus")}, "%", 10)
    svg_bars(out / "graph_b_state_causality_overhead.svg", "State Causality overhead vs RU full", names, {before: pct(before, "state_causality"), after: pct(after, "state_causality")}, "%", 20)
    svg_scatter(out / "graph_c_transitions_vs_runtime.svg", "State Causality runtime vs transition count", "transitions", "runtime_execution_ns",
                {label: [(timings[label][n]["transitions"], timings[label][n]["state_causality"]) for n in CASES] for label in (before, after)})
    svg_scatter(out / "graph_d_reasoning_state_runtime.svg", "reasoning_state_runtime_ns vs transition count", "transitions", "reasoning_state_runtime_ns",
                {label: [(timings[label][n]["transitions"], timings[label][n]["components_ns"]["reasoning_state_runtime_ns"]) for n in CASES] for label in (before, after)})
    svg_scatter(out / "graph_e_causal_runtime_vs_relations.svg", "state_causality_runtime_ns vs relation count", "relations", "state_causality_runtime_ns",
                {label: [(timings[label][n]["relations"], timings[label][n]["components_ns"]["state_causality_runtime_ns"]) for n in CASES] for label in (before, after)})
    if profile:
        svg_scatter(out / "graph_f_allocations_vs_runtime.svg", "allocations vs run time (in-process, State Causality)", "allocations per run", "run_ns",
                    {label: [(profile[label][n]["causality"]["run_allocations"], profile[label][n]["causality"]["run_ns"]) for n in CASES] for label in (before, after)})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", action="append", default=[], metavar="LABEL=PATH")
    parser.add_argument("--profile", action="append", default=[], metavar="LABEL=PATH", help="in-process harness binaries")
    parser.add_argument("--baseline-commit", default=None)
    parser.add_argument("--optimized-commit", default=None)
    parser.add_argument("--build-profile", default="release")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--samples", type=int, default=15)
    parser.add_argument("--profile-iterations", type=int, default=2000)
    args = parser.parse_args()
    parse_pairs = lambda pairs: {label: Path(path).resolve() for label, path in (item.split("=", 1) for item in pairs)}  # noqa: E731
    binaries = parse_pairs(args.binary) or {"current": Path(find_binary()).resolve()}
    profiles = parse_pairs(args.profile)
    labels = list(binaries)
    baseline, optimized = binaries[labels[0]], binaries[labels[-1]]
    dirty = bool(git("status", "--porcelain"))
    head = git("rev-parse", "HEAD")
    timings = measure(binaries, args.warmup, args.samples)
    overhead = {label: overheads(timings[label]) for label in labels}
    final = overhead[labels[-1]]["aggregate"]
    initial = overhead[labels[0]]["aggregate"]
    verdicts = {name: verdict(name, final[name]) for name in LIMITS}
    improvement = {name: initial[name] - final[name] for name in LIMITS}
    if all(v == "PASS" for v in verdicts.values()):
        performance_gate = "PASS"
    elif final["lightweight_rus"] <= LIMITS["lightweight_rus"][1] and final["state_causality"] <= LIMITS["state_causality"][1] and all(improvement[n] > 0.05 for n in LIMITS):
        performance_gate = "PARTIAL_PASS"
    else:
        performance_gate = "HOLD"
    regressions = [
        {"n": n, "config": config, "baseline_ns": timings[labels[0]][n][config], "optimized_ns": timings[labels[-1]][n][config]}
        for n in CASES for config in CONFIGS
        if timings[labels[-1]][n][config] > 1.10 * timings[labels[0]][n][config] and len(labels) > 1
    ]
    checks = equivalence(baseline, optimized) if len(labels) > 1 else None
    profile = in_process(profiles, args.profile_iterations) if profiles else {}
    summary = {
        "schema": "reasonscript-reasoning-state-optimization/1.0",
        "baseline_commit": args.baseline_commit,
        "optimized_commit": args.optimized_commit or head,
        "source_commit": args.optimized_commit or head,
        "benchmark_commit": head,
        "dirty": dirty,
        "working_tree_dirty": dirty,
        "formal_evaluation": not dirty,
        "binaries": {label: {"file": path.name, "runtime_binary_sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for label, path in binaries.items()},
        "compiler_version": subprocess.run(["rustc", "--version"], text=True, capture_output=True).stdout.strip(),
        "os": platform.platform(),
        "cpu_architecture": platform.machine(),
        "build_profile": args.build_profile,
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "warmup": args.warmup,
        "samples": args.samples,
        "timing_boundary": "runtime_execution_ns (run_calculations), identical for every binary",
        "baseline_label": labels[0],
        "optimized_label": labels[-1],
        "overhead": overhead,
        "rus_overhead": {"before": initial["lightweight_rus"], "after": final["lightweight_rus"]},
        "state_causality_overhead": {"before": initial["state_causality"], "after": final["state_causality"]},
        "verdicts": verdicts,
        "performance_gate": performance_gate,
        "regression_guard_over_110_percent_of_baseline": regressions,
        "component_timings_ns": {label: {n: timings[label][n]["components_ns"] for n in CASES} for label in labels},
        "hash_equivalence": checks and {"all_hashes_equal": checks["all_hashes_equal"], "hash_matches": checks["hash_matches"], "cases": checks["cases"]},
        "semantic_equivalence": checks,
        "determinism": determinism(optimized),
        "in_process": profile,
        "in_process_end_to_end": end_to_end(profile, labels),
        "timings_ns": timings,
    }
    write_artifacts(args.out, summary, timings, labels, profile)
    print(json.dumps({k: summary[k] for k in ("working_tree_dirty", "rus_overhead", "state_causality_overhead", "verdicts", "performance_gate", "hash_equivalence", "determinism")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
