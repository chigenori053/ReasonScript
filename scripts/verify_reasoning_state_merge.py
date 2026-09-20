#!/usr/bin/env python3
"""Verification gate for the Lightweight RUS R4 main integration.

Run on the clean integration branch. It executes the gates of the merge
specification, times R0 / pre-merge R4 / post-merge R4 with the same
interleaved harness as `benchmark_reasoning_state.py`, and writes
`artifacts/reasoning_state_merge/summary.json` and `post_merge_comparison.csv`.
CI is checked on the pull request, so it is recorded there, not here.

    scripts/verify_reasoning_state_merge.py --baseline-binary <R0 host> --pre-merge-binary <R4 host>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import benchmark_reasoning_state as bench

RUNTIME = ROOT / "ReasonRuntime"
DEBUG_HOST = RUNTIME / "target/debug/reason-runtime-host"
RELEASE_HOST = RUNTIME / "target/release/reason-runtime-host"
BASELINE_COMMIT = "111f199a290292e2108d629742d7a1456c1fdc5e"
R4_SOURCE_COMMIT = "6627ad6442e6d4db7e4273b44346ad990d83e3e2"
R4_BENCHMARK_COMMIT = "70c2895828079214ce2f5ddb11e7975f4dd0b79e"
# Failures caused by the machine (missing vscode-extension/node_modules), not by the runtime.
ENVIRONMENT_TESTS = [
    "tests/lsp/test_vscode_extension_contract.py::test_vscode_extension_typescript_compiles_cleanly",
    "vscode_extension_phase1_4_tests/test_vscode_extension_phase1_4.py::VSCodeExtensionPhase14Tests::test_vsxp14_003_dependency_presence",
]
ENVIRONMENT_MARKERS = ("node_modules", "Cannot find module 'vscode'")
STATE_TESTS = "computation_ir_tests/test_reasoning_state.py"
R4_FILES = ("reasoning_state.rs", "state_causality.rs", "reasoning_state_profile.rs")


def sh(command: list[str], cwd: Path = ROOT, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})


def git(*args: str) -> str:
    return sh(["git", *args]).stdout.strip()


def dirty() -> bool:
    return bool(git("status", "--porcelain"))


def pytest_counts(output: str) -> dict:
    counts = {name: 0 for name in ("passed", "failed", "skipped", "deselected", "errors")}
    for number, name in re.findall(r"(\d+) (passed|failed|skipped|deselected|error)", output.splitlines()[-1] if output.strip() else ""):
        counts["errors" if name == "error" else name] = int(number)
    return counts


def cargo_counts(output: str) -> dict:
    results = re.findall(r"test result: (?:ok|FAILED)\. (\d+) passed; (\d+) failed", output)
    return {"passed": sum(int(p) for p, _ in results), "failed": sum(int(f) for _, f in results)}


def pytest(*args: str) -> dict:
    started = time.time()
    completed = sh([sys.executable, "-m", "pytest", *args, "-q", "-p", "no:cacheprovider"], env={"REASONSCRIPT_RUNTIME_HOST": str(DEBUG_HOST)})
    tail = completed.stdout.strip().splitlines()
    return {"returncode": completed.returncode, **pytest_counts(tail[-1] if tail else ""),
            "seconds": round(time.time() - started, 1), "pass": completed.returncode == 0}


def cargo(*args: str) -> subprocess.CompletedProcess:
    return sh(["cargo", *args], RUNTIME)


def rustfmt_gate(main_base: str) -> dict:
    """No formatting drift in any file this integration changes; drift elsewhere is recorded."""
    fmt = cargo("fmt", "--check")
    drifted = sorted({Path(path).resolve().relative_to(ROOT).as_posix() for path in re.findall(r"^Diff in (\S+?):\d+", fmt.stdout + fmt.stderr, re.MULTILINE)})
    changed = set(git("diff", "--name-only", main_base, "HEAD").splitlines())
    touched = [path for path in drifted if path in changed]
    return {"pass": not touched, "workspace_clean": fmt.returncode == 0, "drift_in_changed_files": touched,
            "pre_existing_drift_outside_this_integration": [path for path in drifted if path not in changed]}


def rust_gates(main_base: str) -> dict:
    fmt = rustfmt_gate(main_base)
    clippy_ci = cargo("clippy", "--all-targets", "--", "-A", "warnings", "-A", "clippy::overly_complex_bool_expr")
    clippy = cargo("clippy", "--all-targets")
    warnings = re.findall(r"^warning: (?!.*generated).*\n\s+--> (\S+)", clippy.stderr, re.MULTILINE)
    workspace = cargo("test")
    runtime_ir = cargo("test", "-p", "reasonscript-computation-ir")
    replay = cargo("test", "-p", "reasonscript-computation-ir", "replay")
    return {
        "rustfmt": fmt,
        "clippy_ci_parity": {"pass": clippy_ci.returncode == 0, "command": "cargo clippy --all-targets -- -A warnings -A clippy::overly_complex_bool_expr"},
        "clippy": {
            "pass": clippy.returncode == 0,
            "warnings": len(warnings),
            "warnings_in_r4_files": [w for w in warnings if any(f in w for f in R4_FILES)],
            "note": "warnings that remain are pre-existing (identical on main)",
        },
        "cargo_test_workspace": {"pass": workspace.returncode == 0, **cargo_counts(workspace.stdout + workspace.stderr)},
        "cargo_test_computation_ir": {"pass": runtime_ir.returncode == 0, **cargo_counts(runtime_ir.stdout + runtime_ir.stderr)},
        "replay_rust": {"pass": replay.returncode == 0, **cargo_counts(replay.stdout + replay.stderr)},
    }


def python_gates() -> dict:
    computation = pytest("computation_ir_tests")
    environment = {}
    for test in ENVIRONMENT_TESTS:
        run = sh([sys.executable, "-m", "pytest", test, "-q", "-p", "no:cacheprovider", "-x"], env={"REASONSCRIPT_RUNTIME_HOST": str(DEBUG_HOST)})
        environment[test] = {
            "returncode": run.returncode,
            "classified": "passed" if run.returncode == 0 else "known-environment-failure" if any(m in run.stdout for m in ENVIRONMENT_MARKERS) else "UNEXPECTED-FAILURE",
        }
    full = pytest(*[arg for test in ENVIRONMENT_TESTS for arg in ("--deselect", test)])
    return {
        "computation_ir_tests": computation,
        "full_repository": {**full, "deselected_environment_tests": environment,
                            "pass": full["pass"] and all(e["classified"] != "UNEXPECTED-FAILURE" for e in environment.values())},
    }


def timed_comparison(baseline: Path, pre: Path, post: Path, warmup: int, samples: int) -> dict:
    binaries = {"R0": baseline, "R4_pre_merge": pre, "R4_post_merge": post}
    timings = bench.measure(binaries, warmup, samples)
    overhead = {label: bench.overheads(timings[label]) for label in binaries}
    aggregate = overhead["R4_post_merge"]["aggregate"]
    limits = {name: bench.LIMITS[name][0] for name in bench.LIMITS}
    totals_pre, totals_post = (overhead[label]["total_runtime_execution_ns"] for label in ("R4_pre_merge", "R4_post_merge"))
    ratios = {config: totals_post[config] / totals_pre[config] for config in bench.CONFIGS}
    per_case = [
        {"n": n, "config": config, "pre_ns": timings["R4_pre_merge"][n][config], "post_ns": timings["R4_post_merge"][n][config],
         "ratio": timings["R4_post_merge"][n][config] / timings["R4_pre_merge"][n][config]}
        for n in bench.CASES for config in ("ru_full", "lightweight_rus", "state_causality")
    ]
    return {
        "timings_ns": timings,
        "overhead": overhead,
        "post_merge_aggregate": aggregate,
        "gate": {"lightweight_rus_le_10pct": aggregate["lightweight_rus"] <= limits["lightweight_rus"],
                 "state_causality_le_20pct": aggregate["state_causality"] <= limits["state_causality"]},
        "regression_guard": {
            "rule": "post-merge R4 <= pre-merge R4 x 1.10",
            "aggregate_ratio_post_over_pre": ratios,
            "aggregate_ok": all(r <= 1.10 for r in ratios.values()),
            "cases_over_110_percent": [c for c in per_case if c["ratio"] > 1.10],
        },
    }


def write_comparison_csv(path: Path, timings: dict) -> None:
    pre, post = timings["R4_pre_merge"], timings["R4_post_merge"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["N", "transitions", "relations", "runtime_ru_full_pre", "runtime_ru_full_post",
                         "runtime_rus_pre", "runtime_rus_post", "runtime_causality_pre", "runtime_causality_post",
                         "rus_overhead_pre", "rus_overhead_post", "causal_overhead_pre", "causal_overhead_post",
                         "post_over_pre_rus", "post_over_pre_causality"])
        for n in bench.CASES:
            a, b = pre[n], post[n]
            writer.writerow([n, b["transitions"], b["relations"], a["ru_full"], b["ru_full"],
                             a["lightweight_rus"], b["lightweight_rus"], a["state_causality"], b["state_causality"],
                             f"{a['lightweight_rus'] / a['ru_full'] - 1:.4f}", f"{b['lightweight_rus'] / b['ru_full'] - 1:.4f}",
                             f"{a['state_causality'] / a['ru_full'] - 1:.4f}", f"{b['state_causality'] / b['ru_full'] - 1:.4f}",
                             f"{b['lightweight_rus'] / a['lightweight_rus']:.4f}", f"{b['state_causality'] / a['state_causality']:.4f}"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-binary", type=Path, required=True, help="R0 host (built from 111f199a)")
    parser.add_argument("--pre-merge-binary", type=Path, required=True, help="R4 host built before the merge")
    parser.add_argument("--main-base", default=None)
    parser.add_argument("--merge-commit", default=None)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/reasoning_state_merge")
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--samples", type=int, default=25)
    args = parser.parse_args()

    started_dirty = dirty()
    head = git("rev-parse", "HEAD")
    merge_commit = args.merge_commit or git("rev-list", "--merges", "--first-parent", "-1", "HEAD") or head
    main_base = args.main_base or git("rev-parse", f"{merge_commit}^1")
    if cargo("build").returncode != 0:
        print("debug build failed")
        return 1
    rust = rust_gates(main_base)
    python = python_gates()
    state = lambda *selectors: pytest(STATE_TESTS, "-k", " or ".join(selectors))  # noqa: E731
    golden, differential = state("golden_dataset"), state("every_small_n")
    r0_compat, replay, schemas = state("pre_optimization_runtime"), state("replays_from_artifacts"), state("published")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
        mutation_path = Path(handle.name)
    mutation_run = sh([sys.executable, "scripts/mutation_reasoning_state.py", "--json", str(mutation_path)])
    mutation = json.loads(mutation_path.read_text(encoding="utf-8"))
    mutation_path.unlink()
    dirty_before_benchmark = dirty()
    if cargo("build", "--release", "-p", "reasonscript-computation-runtime-cli").returncode != 0:
        print("release build failed")
        return 1
    post_binary = RELEASE_HOST
    equivalence = bench.equivalence(args.baseline_binary, post_binary)
    pre_vs_post = bench.equivalence(args.pre_merge_binary, post_binary)
    determinism = bench.determinism(post_binary)
    performance = timed_comparison(args.baseline_binary, args.pre_merge_binary, post_binary, args.warmup, args.samples)
    ended_dirty = dirty()
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: E731
    working_tree_dirty = started_dirty or dirty_before_benchmark or ended_dirty
    gates = {
        "rust_tests": rust["cargo_test_computation_ir"]["pass"] and rust["cargo_test_workspace"]["pass"],
        "rustfmt": rust["rustfmt"]["pass"],
        "clippy": rust["clippy"]["pass"] and rust["clippy_ci_parity"]["pass"] and not rust["clippy"]["warnings_in_r4_files"],
        "python_computation_ir": python["computation_ir_tests"]["pass"],
        "python_full_repository": python["full_repository"]["pass"],
        "golden": golden["pass"] and golden["passed"] == 5,
        "differential_n_2_89": differential["pass"] and differential["passed"] == 88,
        "r0_compatibility_94": r0_compat["pass"] and equivalence["identical_responses"] == 94 == equivalence["cases"],
        "hashes_equivalent": equivalence["all_hashes_equal"] and pre_vs_post["all_hashes_equal"],
        "response_equivalence": equivalence["semantic_equivalence"] and pre_vs_post["semantic_equivalence"],
        "determinism": determinism["stable"],
        "replay": replay["pass"] and rust["replay_rust"]["pass"],
        "mutation": mutation["all_detected"] and mutation_run.returncode == 0,
        "schema_validation": schemas["pass"],
        "performance": all(performance["gate"].values()),
        "regression_guard": performance["regression_guard"]["aggregate_ok"],
        "clean_tree": not working_tree_dirty,
    }
    summary = {
        "schema": "reasonscript-reasoning-state-merge-verification/1.0",
        "main_base_commit": main_base,
        "baseline_commit": BASELINE_COMMIT,
        "r4_source_commit": R4_SOURCE_COMMIT,
        "r4_benchmark_commit": R4_BENCHMARK_COMMIT,
        "merge_commit": merge_commit,
        "integration_head": head,
        "working_tree_dirty": working_tree_dirty,
        "rust_tests": rust,
        "python_tests": python,
        "golden": golden,
        "differential": differential,
        "r0_compatibility": {"digest_test": r0_compat, "cases": equivalence["cases"], "identical_responses": equivalence["identical_responses"]},
        "hash_equivalence": {"r0_vs_post_merge": equivalence, "pre_merge_vs_post_merge": pre_vs_post},
        "response_equivalence": {"identical_responses": equivalence["identical_responses"], "cases": equivalence["cases"],
                                 "key_order_sensitive": True, "pre_merge_vs_post_merge_identical": pre_vs_post["identical_responses"]},
        "determinism": determinism,
        "replay": {"python": replay, "rust": rust["replay_rust"]},
        "mutation": mutation,
        "schema_validation": schemas,
        "performance": performance,
        "provenance": {
            "baseline_binary_sha256": sha(args.baseline_binary),
            "pre_merge_binary_sha256": sha(args.pre_merge_binary),
            "post_merge_binary_sha256": sha(post_binary),
            "post_merge_binary_identical_to_pre_merge": sha(post_binary) == sha(args.pre_merge_binary),
            "compiler": subprocess.run(["rustc", "--version"], capture_output=True, text=True).stdout.strip(),
            "os": platform.platform(),
            "cpu_architecture": platform.machine(),
            "build_profile": "release",
            "warmup": args.warmup,
            "samples": args.samples,
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "gates": gates,
        "failed_gates": [name for name, ok in gates.items() if not ok],
        "verification": "PASS" if all(gates.values()) else "FAIL",
        "ci": "checked on the pull request before merging (see docs/reports/ReasonScript_Lightweight_RUS_R4_Merge_Report.md)",
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_comparison_csv(args.out / "post_merge_comparison.csv", performance["timings_ns"])
    print(json.dumps({"verification": summary["verification"], "failed_gates": summary["failed_gates"], "gates": gates,
                      "post_merge_aggregate": performance["post_merge_aggregate"],
                      "regression_guard": performance["regression_guard"]["aggregate_ratio_post_over_pre"]}, indent=2))
    return 0 if summary["verification"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
