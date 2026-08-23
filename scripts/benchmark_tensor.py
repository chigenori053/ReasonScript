#!/usr/bin/env python3
"""Tensor Standard Functions micro/operator benchmark harness.

Phase 0 baseline tool from the ReasonScript modernization plan (section 17
"性能評価"): establishes a reproducible, versioned measurement of the current
Python Tensor runtime's per-call cost, so later runtime work (optimizer
passes, a Rust backend, etc.) has a concrete "before" number to compare
against instead of an informal or anecdotal claim.

This only covers what actually exists in this repository today: the
Tensor Standard Functions (`frontend/tensor/runtime.py`). It intentionally
does not attempt the plan's "model" or "experiment" tiers (Transformer
train/eval throughput), because no Transformer fixture exists in this
repository to measure.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend.tensor import TensorRuntime  # noqa: E402

BENCHMARK_SCHEMA = "reasonscript-tensor-benchmark/1.0"
DEFAULT_REPEATS = 200
DEFAULT_WARMUP = 20


def _timed(fn: Callable[[], Any], *, repeats: int, warmup: int) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - start)
    return {
        "repeats": repeats,
        "ns_per_call_mean": statistics.mean(samples),
        "ns_per_call_median": statistics.median(samples),
        "ns_per_call_min": min(samples),
        "ns_per_call_max": max(samples),
    }


def _cases(repeats: int, warmup: int) -> dict[str, dict[str, float]]:
    runtime = TensorRuntime()
    a = runtime.call("tensor.create", [[1.0] * 64 for _ in range(64)], dtype="f32")
    b = runtime.call("tensor.create", [[1.0] * 64 for _ in range(64)], dtype="f32")
    scores = runtime.call("tensor.create", [[float(i) for i in range(32)] for _ in range(32)], dtype="f32")
    index = runtime.call("tensor.create", [0, 1, 2, 3], dtype="i64")

    results: dict[str, dict[str, float]] = {}
    results["cast_dispatch"] = _timed(
        lambda: runtime.call("tensor.shape", a), repeats=repeats, warmup=warmup
    )
    results["elementwise_add_64x64"] = _timed(
        lambda: runtime.call("tensor.add", a, b), repeats=repeats, warmup=warmup
    )
    results["reduction_sum_64x64"] = _timed(
        lambda: runtime.call("tensor.sum", a), repeats=repeats, warmup=warmup
    )
    results["matmul_64x64"] = _timed(
        lambda: runtime.call("tensor.matmul", a, b), repeats=repeats, warmup=warmup
    )
    results["softmax_32x32"] = _timed(
        lambda: runtime.call("tensor.softmax", scores), repeats=repeats, warmup=warmup
    )
    results["gather_64x64"] = _timed(
        lambda: runtime.call("tensor.gather", a, index, axis=0), repeats=repeats, warmup=warmup
    )
    return results


def run_benchmark(repeats: int = DEFAULT_REPEATS, warmup: int = DEFAULT_WARMUP) -> dict[str, Any]:
    return {
        "schema": BENCHMARK_SCHEMA,
        "version": "1.0",
        "tier": "micro_operator",
        "backend": "python-reference",
        "cases": _cases(repeats, warmup),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP)
    parser.add_argument("--out", type=Path, default=None, help="Write JSON report to this path")
    args = parser.parse_args(argv)

    report = run_benchmark(repeats=args.repeats, warmup=args.warmup)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
