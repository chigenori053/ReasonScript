#!/usr/bin/env python3
"""Phase 0 / post-change profile of the reasoning-state hot path.

Runs the in-process harness (`cargo build --release -p reasonscript-computation-runtime-cli
--example reasoning_state_profile`) for one or more builds and reports, per
factorization case and configuration, the run time (the `runtime_execution_ns`
boundary), allocation counts, and the response-construction cost. With
`--sample` (macOS) it also attaches `sample(1)` to a long-running harness and
summarizes the call graph: inclusive samples of the state functions and
self-time by category.

    scripts/profile_reasoning_state.py --profile R0=path/r0-profile --profile R4=path/r4-profile --sample
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frontend.computation_ir import lower_program
from frontend.language_surface import parse

TEMPLATE = (ROOT / "computation_ir_tests/golden_reasoning_state/factorize.rsn.template").read_text(encoding="utf-8")
DEFAULT_OUT = ROOT / "artifacts/reasoning_state_optimization/profile"
CASES = (77, 997, 10007, 30030, 10403)
CONFIGS = ("ru_full", "lightweight", "causality")
STATE_FUNCTIONS = {
    "RuntimeReasoningState::apply": "RuntimeReasoningState::apply",
    "RuntimeReasoningState::effect_of": "RuntimeReasoningState::effect_of",
    "StateCausality::observe": "StateCausality::observe",
    "StateCausality::link_next_ru": "StateCausality::link_next_ru",
    "state_relation (provenance JSON)": "state_causality::state_relation",
    "StateCausality::trace": "StateCausality::trace",
    "state_hash": "reasoning_state::state_hash",
    "transition_hash": "reasoning_state::transition_hash",
    "to_artifact": "to_artifact",
    "serde_json serialization": "serde_json::ser::",
    "serde_json::to_value": "serde_json::value::to_value",
    "BTreeMap": "btree",
    "String clone/alloc": "alloc::string",
    "Value clone/drop": "serde_json..value..Value",
}
SELF_CATEGORIES = {
    "malloc/free": r"malloc|_free|xzm|realloc|rust_alloc|rust_dealloc",
    "memmove/memset": r"memmove|bzero|memset|memcpy",
    "sha256": r"sha2|compress256",
    "serde_json": r"serde_json|serde_core",
    "hash map/index map": r"hashbrown|indexmap|sip|hash_one",
    "clock": r"mach_absolute_time",
}


def harness(binary: Path, program: Path, config: str, iterations: int) -> dict:
    completed = subprocess.run([str(binary), str(program), config, str(iterations)], text=True, capture_output=True, check=True)
    return json.loads(completed.stdout)


def summarize_sample(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    graph = text.split("Call graph:")[1].split("Total number in stack")[0]
    inclusive: collections.Counter = collections.Counter()
    for line in graph.splitlines():
        match = re.match(r"^[\s+!:|]*(\d+)\s+(.*?)\s+\(in ", line)
        if match:
            inclusive[re.sub(r"::h[0-9a-f]{16}$", "", match.group(2))] += int(match.group(1))
    top = text.split("Sort by top of stack")[1]
    self_time: collections.Counter = collections.Counter()
    total_self = 0
    for line in top.splitlines()[1:]:
        match = re.match(r"^\s+(.*?)\s+\(in .*?\)\s+(\d+)$", line)
        if not match:
            continue
        symbol, count = match.group(1), int(match.group(2))
        total_self += count
        for category, pattern in SELF_CATEGORIES.items():
            if re.search(pattern, symbol):
                self_time[category] += count
                break
        else:
            self_time["other"] += count
    return {
        "samples_main": inclusive.get("reasoning_state_profile::main", 0),
        "samples_run_calculations": sum(c for s, c in inclusive.items() if s.endswith("Vm::run_calculations")),
        "inclusive_samples": {
            name: sum(count for symbol, count in inclusive.items() if pattern in symbol) for name, pattern in STATE_FUNCTIONS.items()
        },
        "self_samples_by_category": dict(self_time.most_common()),
        "self_samples_total": total_self,
    }


def sample(label: str, binary: Path, program: Path, out: Path) -> dict:
    process = subprocess.Popen([str(binary), str(program), "causality", "60000"], stdout=subprocess.DEVNULL)
    try:
        time.sleep(1.5)
        raw = out / f"sample_{label}.txt"
        subprocess.run(["sample", str(process.pid), "5", "1", "-file", str(raw)], capture_output=True, check=True)
    finally:
        process.kill()
    summary = summarize_sample(raw)
    with gzip.open(out / f"sample_{label}.txt.gz", "wt", encoding="utf-8") as handle:
        handle.write(raw.read_text(encoding="utf-8"))
    raw.unlink()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", action="append", required=True, metavar="LABEL=PATH")
    parser.add_argument("--iterations", type=int, default=3000)
    parser.add_argument("--sample", action="store_true", help="attach sample(1) (macOS)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    profiles = {label: Path(path).resolve() for label, path in (item.split("=", 1) for item in args.profile)}
    args.out.mkdir(parents=True, exist_ok=True)
    result: dict = {"cases": list(CASES), "in_process": {}, "sample": {}}
    with tempfile.TemporaryDirectory() as directory:
        programs = {}
        for n in CASES:
            programs[n] = Path(directory) / f"program-{n}.json"
            programs[n].write_text(json.dumps(lower_program(parse(TEMPLATE.replace("__N__", str(n))))), encoding="utf-8")
        for label, binary in profiles.items():
            for n in CASES:
                for config in CONFIGS:
                    result["in_process"].setdefault(label, {}).setdefault(str(n), {})[config] = harness(binary, programs[n], config, args.iterations)
            if args.sample:
                result["sample"][label] = sample(label, binary, programs[10403], args.out)
    # per-transition hot-path allocations relative to executable RU full
    for label, cases in result["in_process"].items():
        for n, configs in cases.items():
            transitions = configs["causality"]["state_revisions"] or 1
            for config in ("lightweight", "causality"):
                configs[config]["hot_path_allocations_per_transition"] = round(
                    (configs[config]["run_allocations"] - configs["ru_full"]["run_allocations"]) / transitions, 2
                )
    (args.out / "profile.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for label, cases in result["in_process"].items():
        for n, configs in cases.items():
            base = configs["ru_full"]
            print(
                label, n,
                *(f"{c}: +{100 * (configs[c]['run_ns'] / base['run_ns'] - 1):.1f}% run, {configs[c]['hot_path_allocations_per_transition']} allocs/transition, mat {configs[c]['materialize_ns']}ns"
                  for c in ("lightweight", "causality")),
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
