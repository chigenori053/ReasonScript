#!/usr/bin/env python3
"""Graphs for Adaptive / Cost-Aware Constraint Fusion v0.1 (spec section
94-98). Run under a matplotlib-equipped interpreter, e.g.:

    ~/development/ReasonScript_SpecTest/.venv/bin/python3 \
        scripts/make_adaptive_fusion_graphs.py
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> list[dict]:
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    bool_keys = {"results_identical", "b_comparable"}
    text_keys = {"test_id", "problem_class", "search_space_bucket"} | bool_keys
    rows = [row for row in rows if row.get("results_identical") == "True"]
    for row in rows:
        for key, value in row.items():
            if key in bool_keys:
                row[key] = value == "True"
            elif key not in text_keys:
                row[key] = float(value) if value not in ("", "None") else None
    return rows


def k_of(problem_class: str) -> int | None:
    return int(problem_class.replace("synthetic_k", "")) if problem_class.startswith("synthetic_k") else None


def graph_a_k_vs_rter(rows: list[dict], out: Path) -> None:
    synth = [r for r in rows if r["b_comparable"] and k_of(r["problem_class"]) is not None]
    by_target: dict[float, list[dict]] = {}
    for r in synth:
        by_target.setdefault(r["search_space_target"], []).append(r)
    fig, axes = plt.subplots(1, len(by_target), figsize=(4.5 * len(by_target), 4.5), sharey=True)
    for ax, target in zip(axes, sorted(by_target)):
        pts = sorted(by_target[target], key=lambda r: k_of(r["problem_class"]))
        ks = [k_of(r["problem_class"]) for r in pts]
        ax.plot(ks, [r["RTER_E_B"] for r in pts], "o--", label="E", alpha=0.6)
        ax.plot(ks, [r["RTER_F_B"] for r in pts], "o--", label="F", alpha=0.6)
        ax.plot(ks, [r["RTER_G_B"] for r in pts], "o-", label="G", linewidth=2)
        ax.axhline(1.0, color="black", linestyle=":", linewidth=1)
        ax.set_title(f"target={target:,.0f}")
        ax.set_xlabel("k")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("RTER vs Model B")
    axes[0].legend()
    fig.suptitle("k vs RTER: Model E / F / G")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def graph_b_search_space_vs_runtime(rows: list[dict], out: Path) -> None:
    synth = [r for r in rows if r["problem_class"] in ("synthetic_k4", "synthetic_k6")]
    fig, ax = plt.subplots(figsize=(7, 5))
    colors = {"synthetic_k4": "tab:blue", "synthetic_k6": "tab:orange"}
    for cls, color in colors.items():
        pts = sorted([r for r in synth if r["problem_class"] == cls], key=lambda r: r["sqrt_N"])
        for model, style in (("E", "--"), ("F", ":"), ("G", "-")):
            ax.plot([p["sqrt_N"] for p in pts], [p[f"runtime_{model}"] for p in pts], style, color=color, marker="o", label=f"{cls}, {model}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("search space size (sqrt(N))")
    ax.set_ylabel("runtime_execution_ns (median)")
    ax.set_title("Runtime vs Search Space (dashed=E, dotted=F, solid=G)")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def graph_c_heatmap(rows: list[dict], out: Path) -> None:
    synth = [r for r in rows if r["b_comparable"] and k_of(r["problem_class"]) is not None]
    targets = sorted({r["search_space_target"] for r in synth})
    ks = sorted({k_of(r["problem_class"]) for r in synth})
    grid = [[None] * len(targets) for _ in ks]
    for r in synth:
        ki, ti = ks.index(k_of(r["problem_class"])), targets.index(r["search_space_target"])
        grid[ki][ti] = r["RTER_G_B"]
    array = np.array([[v if v is not None else np.nan for v in row] for row in grid])
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(array, cmap="RdYlGn", vmin=0.2, vmax=1.8, aspect="auto")
    ax.set_xticks(range(len(targets)))
    ax.set_xticklabels([f"{t:,.0f}" for t in targets], rotation=30, ha="right")
    ax.set_yticks(range(len(ks)))
    ax.set_yticklabels([f"k={k}" for k in ks])
    ax.set_xlabel("target search space size (sqrt(N))")
    ax.set_ylabel("compression level (k)")
    ax.set_title("Model G RTER vs Model B (green = G faster, red = B faster)")
    for i in range(len(ks)):
        for j in range(len(targets)):
            if grid[i][j] is not None:
                ax.text(j, i, f"{grid[i][j]:.2f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, label="RTER_G_B")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def graph_d_score_vs_improvement(rows: list[dict], out: Path) -> None:
    """spec section 97: predicted fusion desirability (here: how much G
    diverges from F, i.e. how often/aggressively it rejected fusion) vs
    actual F-to-E improvement -- a proxy since per-decision scores aren't
    exported to the benchmark CSV (only aggregate counters are, per spec
    section 38's "debug/profile mode only" restriction)."""
    synth = [r for r in rows if r["b_comparable"] and k_of(r["problem_class"]) is not None]
    fig, ax = plt.subplots(figsize=(7, 5))
    x = [(r["fusion_rejected_cost_G"] or 0) / max(1, (r["fusion_candidate_G"] or 1)) for r in synth]
    y = [r["GRF"] for r in synth]
    ax.scatter(x, y, alpha=0.6)
    ax.axhline(1.0, color="black", linestyle=":", linewidth=1)
    ax.set_xlabel("fraction of fusion candidates rejected by cost (Model G)")
    ax.set_ylabel("GRF = runtime_F / runtime_G (>1 means G faster than F)")
    ax.set_title("Cost-rejection rate vs realized speedup over Always-Fusion")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-dir", type=Path, default=ROOT / "artifacts/adaptive_fusion_profile")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()
    out_dir = args.out_dir or (args.in_dir / "graphs")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = load(args.in_dir / "comparison.csv")
    graph_a_k_vs_rter(rows, out_dir / "k_vs_rter.png")
    graph_b_search_space_vs_runtime(rows, out_dir / "search_space_vs_runtime.png")
    graph_c_heatmap(rows, out_dir / "rter_heatmap.png")
    graph_d_score_vs_improvement(rows, out_dir / "cost_rejection_vs_speedup.png")
    print(f"wrote 4 graphs to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
