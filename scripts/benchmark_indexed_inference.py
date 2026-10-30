#!/usr/bin/env python3
"""Run frozen MRA_Test inputs on the indexed native ReasonScript entry.

Read-only access to MRA_Test; each line retains outcome, elapsed time, and hashes.
Timings include input encoding, native process startup, ABI decoding, and inference.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from frontend.computation_ir import lower_program
from frontend.computation_ir.optimizer import optimize_program
from frontend.computation_ir.rust_bridge import run_ir
from frontend.language_surface import parse, validate


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mra-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seeds', nargs='+', type=int, default=[401, 402, 403])
    parser.add_argument('--sizes', nargs='+', type=int, default=[10000, 100000])
    parser.add_argument('--depths', nargs='+', type=int, default=[2, 4, 8, 16])
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--host', type=Path, default=ROOT/'ReasonRuntime/target/release/reason-runtime-host')
    parser.add_argument('--source', type=Path, default=ROOT/'examples/inference_scale/main.rsn')
    args = parser.parse_args()
    base = args.mra_root/'experiments/quantum-state-unified-ru-v011-rs/reports/run-20261030-rs-02/raw'
    ast = parse(args.source.read_text()); validate(ast)
    ir = optimize_program(lower_program(ast))
    host = args.host.resolve(strict=True)
    host_hash = digest(host)
    source_hash = digest(args.source)
    failed = False
    # Exclusive creation protects earlier measurements.
    with args.out.open('x') as output:
        for family in ('random', 'math'):
            for seed in args.seeds:
                for size in args.sizes:
                    path = base/f'rs-input-r3-{family}-{seed}-{size}.json'
                    inputs = json.loads(path.read_text())
                    for depth in args.depths:
                        oracle_path = base/f'oracle-r3-{family}-{seed}-{size}-{depth}.json'
                        oracle = json.loads(oracle_path.read_text())
                        inputs.update(depth=depth)
                        if family == 'math':
                            inputs['goal'] = 2**depth
                        for repeat in range(args.repeats):
                            start = time.perf_counter()
                            row = dict(family=family, seed=seed, size=size, depth=depth,
                                       repeat=repeat, source_sha256=source_hash, host_sha256=host_hash,
                                       input_sha256=digest(path), oracle_sha256=digest(oracle_path))
                            try:
                                result = run_ir(ir, binary=host, entry='UnifiedB::Derive', inputs=inputs,
                                    semantic_events=False, benchmark_metrics=True,
                                    limits=dict(max_input_elements=5_000_000,
                                                max_input_bytes=536_870_912,
                                                max_loop_iterations=10_000_000))
                                value = next(iter(result.calculation_results.values()))['fields'] if result.ok else None
                                valid = bool(result.ok and value['admitted'] and not value['resource_limit']
                                             and value['status'] == oracle['status']
                                             and sorted(value['dependencies']) == oracle['unknown_dependencies']
                                             and value['all_paths'] == oracle['proof_paths'])
                                row.update(valid=valid, result=value, error_code=result.error_code,
                                           metadata=result.metadata)
                            except subprocess.TimeoutExpired:
                                row.update(valid=False, error_code='RTH-TIMEOUT-001')
                            row['seconds'] = time.perf_counter() - start
                            failed |= not row['valid']
                            output.write(json.dumps(row, ensure_ascii=False)+'\n'); output.flush()
                            print(f"{family} seed={seed} n={size} depth={depth} repeat={repeat}: "
                                  f"{'PASS' if row['valid'] else 'FAIL'} {row['seconds']:.3f}s", flush=True)
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
