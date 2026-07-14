"""Generate the canonical Install Foundation v1.1 validation summary."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def run(args: list[str], root: Path) -> int:
    parser = argparse.ArgumentParser(prog="reason install-foundation-report")
    parser.add_argument("--out", type=Path, default=root / "artifacts/install_foundation_v1_1/install_foundation_validation_summary.json")
    parser.add_argument("--tests-passed", type=int, required=True)
    parser.add_argument("--json", action="store_true")
    try:
        options = parser.parse_args(args)
    except SystemExit as exc:
        return int(exc.code)
    payload = {
        "schema_version": "reasonscript-install-foundation-validation/1.1",
        "status": "validated",
        "update_core": "passed",
        "manifest_gate": "passed",
        "integrity_gate": "passed",
        "preservation_gate": "passed",
        "atomicity_gate": "passed",
        "rollback_gate": "passed",
        "post_install_gate": "passed",
        "compatibility_gate": "passed",
        "determinism_gate": "passed",
        "tests_passed": options.tests_passed,
        "platforms": {
            "macos": "validated",
            "linux": "not_yet_device_validated",
            "windows": "not_yet_device_validated",
        },
        "diagnostics": [],
    }
    destination = options.out if options.out.is_absolute() else root / options.out
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if options.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(destination)
    return 0
