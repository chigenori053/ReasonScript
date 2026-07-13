"""CLI wrapper for ``reason project-validate``."""

from __future__ import annotations

import json
from pathlib import Path

from .project_validation import validate_project, write_project_validation_report


def run(args: list[str], project_root: Path) -> int:
    positional = [item for item in args if not item.startswith("--")]
    root = (project_root / positional[0]).resolve() if positional else project_root.resolve()
    report = validate_project(root)
    write_project_validation_report(root, report)
    if "--json" in args:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Project validation {report['status']}.")
        print(f"Sources: {report['sources_passed']}/{report['sources_total']}")
    return 0 if report["status"] == "passed" else 1
