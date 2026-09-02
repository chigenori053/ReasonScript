#!/usr/bin/env python3
"""Reproducible UERA-8 Relation Matrix optimization benchmark."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend.computation_ir import interpret_program, lower_program, validate_program
from frontend.computation_ir.optimizer import optimize_program
from frontend.language_surface import parse

DEFAULT_FIXTURE = ROOT / "benchmarks" / "relation_matrix.rsn"
SCHEMA = "reasonscript-relation-matrix-benchmark/1.0"
TARGET_SECONDS = 1.5


def _measure(ir: dict, samples: int) -> tuple[float, dict]:
    durations: list[float] = []
    result: dict = {}
    for _ in range(samples):
        started = time.perf_counter()
        outcome = interpret_program(ir)
        durations.append(time.perf_counter() - started)
        result = dict(outcome.calculation_results)
    return statistics.median(durations), result


def benchmark(fixture: Path, samples: int) -> dict:
    source = fixture.read_text(encoding="utf-8")
    unoptimized = lower_program(parse(source))
    optimized = optimize_program(unoptimized)
    errors = validate_program(optimized)
    if errors:
        raise ValueError("optimized IR is invalid: " + "; ".join(errors))
    unoptimized_seconds, expected = _measure(unoptimized, samples)
    optimized_seconds, actual = _measure(optimized, samples)
    if actual != expected:
        raise ValueError(f"optimization changed result: {expected!r} != {actual!r}")
    return {
        "schema": SCHEMA,
        "fixture": str(fixture.relative_to(ROOT)),
        "samples": samples,
        "result": actual,
        "unoptimized_median_seconds": unoptimized_seconds,
        "optimized_median_seconds": optimized_seconds,
        "speedup": unoptimized_seconds / optimized_seconds,
        "target_seconds": TARGET_SECONDS,
        "target_met": optimized_seconds <= TARGET_SECONDS,
        "parity": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--samples", type=int, default=25)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be positive")
    payload = benchmark(args.fixture.resolve(), args.samples)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.check and not payload["target_met"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
