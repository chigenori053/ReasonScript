#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAYERS = {
    0: "ast_validation_tests",
    1: "default_expansion_tests",
    2: "policy_tests",
    3: "lowering_tests",
    4: "reason_ir_tests",
    5: "end_to_end_tests",
}


def main() -> int:
    results = []
    for layer, suite in LAYERS.items():
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                f"frontend/compiler_conformance/{suite}",
                "-p",
                "test_*.py",
                "-v",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        result = {
            "layer": layer,
            "suite": suite,
            "status": "pass" if completed.returncode == 0 else "fail",
            "output": (completed.stdout + completed.stderr).strip(),
        }
        results.append(result)
        print(f"Layer {layer}: {result['status'].upper()}")

    report = {
        "framework_version": "0.1",
        "compiler_version": "compiler/0.1",
        "ast_abi_version": "reasonscript-ast/0.1",
        "reason_ir_version": "reason-ir/0.1",
        "generated_on": date.today().isoformat(),
        "layers": results,
    }
    reports = ROOT / "frontend" / "compiler_conformance" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "compiler_conformance_results_v0.1.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0 if all(item["status"] == "pass" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
