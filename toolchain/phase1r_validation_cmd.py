from __future__ import annotations

import json
from pathlib import Path

from .phase1r_validation import run_phase1r_validation


def run(args: list[str], root: Path) -> int:
    summary = run_phase1r_validation(root, regression_passed="--regression-passed" in args)
    if "--json" in args:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Phase 1R validation {summary['status']}.")
    return 0 if summary["status"] in {"implemented", "validated"} else 1
