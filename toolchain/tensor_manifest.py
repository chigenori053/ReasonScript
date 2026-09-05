"""Tensor Standard Functions contract manifest (reasonscript-tensor-function-manifest/1.0).

Implements the "契約manifest化" baseline task from the ReasonScript
modernization plan (Phase 0): freeze the full argument/return/diagnostic
contract of every `tensor.*` function so future changes to the Tensor
runtime are caught as an explicit, reviewable diff instead of silent drift.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from frontend.tensor.contracts import tensor_function_contracts

MANIFEST_SCHEMA = "reasonscript-tensor-function-manifest/1.0"
DEFAULT_BASELINE_PATH = Path("contracts/tensor_function_manifest.json")


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def build_manifest() -> dict[str, Any]:
    contracts = tensor_function_contracts()
    functions = {name: contract.to_dict() for name, contract in contracts.items()}
    return {
        "schema": MANIFEST_SCHEMA,
        "version": "1.0",
        "function_count": len(functions),
        "functions": functions,
    }


def write_manifest(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(build_manifest()), encoding="utf-8")
    return path


def diff_manifest(baseline_path: Path) -> list[str]:
    """Compare the live contract set against a committed baseline manifest.

    Returns a list of human-readable differences; empty means the live
    contract surface matches the frozen baseline exactly.
    """
    current = build_manifest()
    if not baseline_path.is_file():
        return [f"baseline manifest not found: {baseline_path}"]
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"baseline manifest unreadable: {baseline_path} ({error})"]

    diffs: list[str] = []
    baseline_functions: dict[str, Any] = baseline.get("functions", {})
    current_functions: dict[str, Any] = current["functions"]

    added = sorted(set(current_functions) - set(baseline_functions))
    removed = sorted(set(baseline_functions) - set(current_functions))
    for name in added:
        diffs.append(f"function added since baseline: {name}")
    for name in removed:
        diffs.append(f"function removed since baseline: {name}")

    for name in sorted(set(current_functions) & set(baseline_functions)):
        if current_functions[name] != baseline_functions[name]:
            diffs.append(f"contract changed for {name}")

    return diffs
