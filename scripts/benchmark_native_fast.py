#!/usr/bin/env python3
"""Phase 9 benchmark: `NumericMode::CompatReference` vs `NativeFast`.

Measures the actual, current speedup the Rust computation runtime's
parallel (`rayon`) op paths give on this machine, for a representative
Tensor-heavy workload (matmul + elementwise), by shelling out to the
built `reason-computation-runtime` binary with
`REASONSCRIPT_NUMERIC_MODE` set to each mode. Reports real measured
numbers only -- this is deliberately NOT validated against the plan's
Phase 9 gate ("現行比10倍以上", tied to true parallel CPU *and* BLAS
*and* GPU, none of which except plain CPU parallelism are in scope here
-- see AGENTS.md), and this repository has no Transformer/Model D
fixture to measure "accuracy低下0.1pt以内" against either.

Usage:
    python3 scripts/benchmark_native_fast.py [--size N] [--repeats N]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend.computation_ir import lower_program  # noqa: E402
from frontend.computation_ir.rust_bridge import find_binary  # noqa: E402
from frontend.language_surface import parse  # noqa: E402


def _workload(size: int) -> dict:
    source = f"""
    module M {{
        calculation Answer {{
            let a = tensor.random_uniform([{size}, {size}], 0.0, 1.0, 42)
            let b = tensor.random_uniform([{size}, {size}], 0.0, 1.0, 43)
            let c = tensor.matmul(a, b)
            let d = tensor.add(c, c)
            let e = tensor.sum(d, [0], false)
            result = tensor.shape(e)
        }}
    }}
    """
    return lower_program(parse(source))


def _timed_runs(binary: Path, payload: str, mode: str | None, *, repeats: int, warmup: int) -> list[float]:
    import os

    env = dict(os.environ)
    if mode is not None:
        env["REASONSCRIPT_NUMERIC_MODE"] = mode
    else:
        env.pop("REASONSCRIPT_NUMERIC_MODE", None)
    for _ in range(warmup):
        subprocess.run([str(binary)], input=payload, capture_output=True, text=True, env=env, check=True)
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        result = subprocess.run(
            [str(binary)], input=payload, capture_output=True, text=True, env=env, check=True
        )
        samples.append(time.perf_counter() - start)
        if not json.loads(result.stdout)["ok"]:
            raise RuntimeError(f"workload failed: {result.stdout}")
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=600, help="matmul operand side length")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    binary = find_binary()
    if binary is None:
        print("reason-computation-runtime binary not built; run `cargo build --release`", file=sys.stderr)
        return 1

    payload = json.dumps(_workload(args.size))
    compat_samples = _timed_runs(binary, payload, None, repeats=args.repeats, warmup=args.warmup)
    fast_samples = _timed_runs(binary, payload, "native-fast", repeats=args.repeats, warmup=args.warmup)
    compat_best, fast_best = min(compat_samples), min(fast_samples)

    report = {
        "schema": "reasonscript-native-fast-benchmark/0.1",
        "workload": f"matmul({args.size}x{args.size}) + add + sum(axis=0)",
        "repeats": args.repeats,
        "compat_reference_seconds_best": compat_best,
        "native_fast_seconds_best": fast_best,
        "speedup": compat_best / fast_best,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"workload: {report['workload']}")
        print(f"compat-reference (best of {args.repeats}): {compat_best:.4f}s")
        print(f"native-fast      (best of {args.repeats}): {fast_best:.4f}s")
        print(f"speedup: {report['speedup']:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
