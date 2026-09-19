#!/usr/bin/env python3
"""Graphs for the Reasoning-to-Resource Efficiency Test v1.0 (spec section
30). Reads comparison.csv (written by benchmark_reasoning_resource_efficiency.py)
and needs nothing from the ReasonScript frontend, so it runs fine under a
separate matplotlib-equipped interpreter, e.g.:

    ~/development/ReasonScript_SpecTest/.venv/bin/python3 \
        scripts/make_reasoning_resource_efficiency_graphs.py
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

COLORS = {
    "prime": "tab:red", "semiprime": "tab:brown", "semiprime_near_equal": "tab:pink",
    "repeated_factor_composite": "tab:purple", "highly_composite": "tab:blue",
    "mixed_factor_composite": "tab:green", "mixed": "tab:orange",
}
SYNTHETIC_COLOR = "tab:cyan"


def load(path: Path) -> list[dict]:
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    # Excluded from the summary's aggregate stats (spec section 5's fairness
    # condition doesn't hold for these rows); keep graphs consistent with it.
    rows = [row for row in rows if row.get("results_identical") != "False"]
    text_keys = ("test_id", "problem_class", "search_space_bucket", "termination_B", "termination_E", "results_identical")
    for row in rows:
        for key, value in row.items():
            if key in text_keys:
                continue
            row[key] = float(value) if value not in ("", "None") else None
    return rows


def color_for(problem_class: str) -> str:
    if problem_class.startswith("synthetic"):
        return SYNTHETIC_COLOR
    return COLORS.get(problem_class, "tab:gray")


def graph_rcr_vs_rter(rows: list[dict], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 5))
    for row in rows:
        if row["RCR"] is None or row["RTER"] is None:
            continue
        ax.scatter(row["RCR"], row["RTER"], color=color_for(row["problem_class"]), alpha=0.7, s=28)
    ax.axhline(1.0, color="black", linestyle="--", linewidth=1, label="break-even (RTER = 1)")
    ax.set_xlabel("Reasoning Compression Ratio (RCR = candidate_tests_B / hypothesis_tests_E)")
    ax.set_ylabel("Runtime Efficiency Ratio (RTER = runtime_ns_B / runtime_ns_E)")
    ax.set_title("Compression vs Runtime Efficiency (Model E vs Model B)")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def graph_search_space_vs_runtime(rows: list[dict], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 5))
    synth = [r for r in rows if r["problem_class"].startswith("synthetic")]
    by_k: dict[str, list[dict]] = {}
    for r in synth:
        by_k.setdefault(r["problem_class"], []).append(r)
    cmap = plt.get_cmap("viridis")
    ks = sorted(by_k, key=lambda name: int(name.replace("synthetic_k", "")))
    for index, k in enumerate(ks):
        pts = sorted(by_k[k], key=lambda r: r["sqrt_N"])
        color = cmap(index / max(1, len(ks) - 1))
        ax.plot([p["sqrt_N"] for p in pts], [p["runtime_ns_B"] for p in pts], "o--", color=color, alpha=0.5, label=f"B, {k}")
        ax.plot([p["sqrt_N"] for p in pts], [p["runtime_ns_E"] for p in pts], "o-", color=color, label=f"E, {k}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Search space size (sqrt(N))")
    ax.set_ylabel("runtime_execution_ns (median)")
    ax.set_title("Runtime vs Search Space Size (dashed = Model B, solid = Model E)")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def graph_rcr_vs_vm_ratio(rows: list[dict], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 5))
    for row in rows:
        if row["RCR"] is None or row["POR"] is None:
            continue
        ax.scatter(row["RCR"], row["POR"], color=color_for(row["problem_class"]), alpha=0.7, s=28)
    ax.axhline(1.0, color="black", linestyle="--", linewidth=1)
    ax.set_xlabel("Reasoning Compression Ratio (RCR)")
    ax.set_ylabel("Physical Operation Ratio (POR = vm_instr_B / vm_instr_E)")
    ax.set_title("Compression vs VM Instruction Reduction")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def graph_break_even_map(rows: list[dict], out: Path) -> None:
    synth = [r for r in rows if r["problem_class"].startswith("synthetic")]
    targets = sorted({r["search_space_target"] for r in synth if r["search_space_target"]})
    ks = sorted({int(r["problem_class"].replace("synthetic_k", "")) for r in synth})
    grid = [[None] * len(targets) for _ in ks]
    for row in synth:
        if row["search_space_target"] not in targets:
            continue
        ki = ks.index(int(row["problem_class"].replace("synthetic_k", "")))
        ti = targets.index(row["search_space_target"])
        grid[ki][ti] = row["RTER"]
    fig, ax = plt.subplots(figsize=(6, 5))
    import numpy as np

    array = np.array([[v if v is not None else np.nan for v in row] for row in grid])
    im = ax.imshow(array, cmap="RdYlGn", vmin=0.5, vmax=2.0, aspect="auto")
    ax.set_xticks(range(len(targets)))
    ax.set_xticklabels([f"{t:,}" for t in targets])
    ax.set_yticks(range(len(ks)))
    ax.set_yticklabels([f"k={k}" for k in ks])
    ax.set_xlabel("target search space size (sqrt(N))")
    ax.set_ylabel("compression level (k small factors)")
    ax.set_title("RTER heatmap (green = E faster, red = B faster)")
    for i in range(len(ks)):
        for j in range(len(targets)):
            if grid[i][j] is not None:
                ax.text(j, i, f"{grid[i][j]:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label="RTER")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-dir", type=Path, default=ROOT / "artifacts/reasoning_resource_efficiency")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()
    out_dir = args.out_dir or (args.in_dir / "graphs")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = load(args.in_dir / "comparison.csv")
    graph_rcr_vs_rter(rows, out_dir / "rcr_vs_rter.png")
    graph_search_space_vs_runtime(rows, out_dir / "search_space_vs_runtime.png")
    graph_rcr_vs_vm_ratio(rows, out_dir / "rcr_vs_vm_ratio.png")
    graph_break_even_map(rows, out_dir / "break_even_map.png")
    print(f"wrote 4 graphs to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
