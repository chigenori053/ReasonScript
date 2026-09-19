#!/usr/bin/env python3
"""Graphs for Constraint Fusion v0.1 (spec section 52). Run under a
matplotlib-equipped interpreter, e.g.:

    ~/development/ReasonScript_SpecTest/.venv/bin/python3 \
        scripts/make_constraint_fusion_graphs.py
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
    bool_keys = {"b_e_identical", "e_f_identical"}
    text_keys = {"test_id", "problem_class", "search_space_bucket"} | bool_keys
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
    synth = [r for r in rows if r["e_f_identical"] and r["b_e_identical"] and k_of(r["problem_class"]) is not None]
    by_target: dict[float, list[dict]] = {}
    for r in synth:
        by_target.setdefault(r["search_space_target"], []).append(r)
    fig, ax = plt.subplots(figsize=(7, 5))
    cmap = plt.get_cmap("viridis")
    targets = sorted(by_target)
    for i, target in enumerate(targets):
        pts = sorted(by_target[target], key=lambda r: k_of(r["problem_class"]))
        color = cmap(i / max(1, len(targets) - 1))
        ax.plot([k_of(r["problem_class"]) for r in pts], [r["RTER_E_B"] for r in pts], "o--", color=color, alpha=0.5, label=f"E, target={target:,.0f}")
        ax.plot([k_of(r["problem_class"]) for r in pts], [r["RTER_F_B"] for r in pts], "o-", color=color, label=f"F, target={target:,.0f}")
    ax.axhline(1.0, color="black", linestyle=":", linewidth=1)
    ax.set_xlabel("compression level (k small factors)")
    ax.set_ylabel("Runtime Efficiency Ratio vs Model B (RTER)")
    ax.set_title("k vs RTER: Model E (dashed) vs Model F (solid)")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def graph_b_k_vs_constraint_eval(rows: list[dict], out: Path) -> None:
    synth = [r for r in rows if r["e_f_identical"] and k_of(r["problem_class"]) is not None]
    by_k: dict[int, list[dict]] = {}
    for r in synth:
        by_k.setdefault(k_of(r["problem_class"]), []).append(r)
    ks = sorted(by_k)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(ks, [np.median([r["constraint_eval_E"] for r in by_k[k]]) for k in ks], "o--", label="Model E")
    ax.plot(ks, [np.median([r["constraint_eval_F"] for r in by_k[k]]) for k in ks], "o-", label="Model F")
    ax.set_yscale("log")
    ax.set_xlabel("compression level (k small factors)")
    ax.set_ylabel("candidate_constraint_eval_count (median, log scale)")
    ax.set_title("k vs Constraint Evaluation Count")
    ax.legend()
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def graph_c_search_space_vs_runtime(rows: list[dict], out: Path) -> None:
    synth = [r for r in rows if r["e_f_identical"] and r["b_e_identical"] and r["problem_class"] in ("synthetic_k2", "synthetic_k4")]
    fig, ax = plt.subplots(figsize=(7, 5))
    colors = {"synthetic_k2": "tab:blue", "synthetic_k4": "tab:orange"}
    for cls, color in colors.items():
        pts = sorted([r for r in synth if r["problem_class"] == cls], key=lambda r: r["sqrt_N"])
        for model, style in (("B", ":"), ("E", "--"), ("F", "-")):
            ax.plot([p["sqrt_N"] for p in pts], [p[f"runtime_{model}"] for p in pts], style, color=color, marker="o",
                     label=f"{cls}, {model}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("search space size (sqrt(N))")
    ax.set_ylabel("runtime_execution_ns (median)")
    ax.set_title("Runtime vs Search Space Size (dotted=B, dashed=E, solid=F)")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def graph_d_heatmap(rows: list[dict], out: Path) -> None:
    synth = [r for r in rows if r["e_f_identical"] and r["b_e_identical"] and k_of(r["problem_class"]) is not None]
    targets = sorted({r["search_space_target"] for r in synth})
    ks = sorted({k_of(r["problem_class"]) for r in synth})
    grid = [[None] * len(targets) for _ in ks]
    for r in synth:
        ki, ti = ks.index(k_of(r["problem_class"])), targets.index(r["search_space_target"])
        grid[ki][ti] = r["RTER_F_B"]
    array = np.array([[v if v is not None else np.nan for v in row] for row in grid])
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(array, cmap="RdYlGn", vmin=0.2, vmax=1.8, aspect="auto")
    ax.set_xticks(range(len(targets)))
    ax.set_xticklabels([f"{t:,.0f}" for t in targets], rotation=30, ha="right")
    ax.set_yticks(range(len(ks)))
    ax.set_yticklabels([f"k={k}" for k in ks])
    ax.set_xlabel("target search space size (sqrt(N))")
    ax.set_ylabel("compression level (k)")
    ax.set_title("Model F RTER vs Model B (green = F faster, red = B faster)")
    for i in range(len(ks)):
        for j in range(len(targets)):
            if grid[i][j] is not None:
                ax.text(j, i, f"{grid[i][j]:.2f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, label="RTER_F_B")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-dir", type=Path, default=ROOT / "artifacts/constraint_fusion_profile")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()
    out_dir = args.out_dir or (args.in_dir / "graphs")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = load(args.in_dir / "comparison.csv")
    graph_a_k_vs_rter(rows, out_dir / "k_vs_rter.png")
    graph_b_k_vs_constraint_eval(rows, out_dir / "k_vs_constraint_eval.png")
    graph_c_search_space_vs_runtime(rows, out_dir / "search_space_vs_runtime.png")
    graph_d_heatmap(rows, out_dir / "rter_heatmap.png")
    print(f"wrote 4 graphs to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
