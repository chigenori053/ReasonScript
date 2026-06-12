#!/usr/bin/env python3
"""Run all conformance layers and write machine/human-readable reports."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from conformance.framework import ROOT, certification_for

LAYERS = {
    0: "schema_conformance_tests",
    1: "dto_conformance_tests",
    2: "runtime_conformance_tests",
    3: "transaction_conformance_tests",
    4: "platform_conformance_tests",
}


def run_layer(layer: int, directory: str) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            f"conformance/{directory}",
            "-p",
            "test_*.py",
            "-v",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    output = completed.stdout + completed.stderr
    return {
        "layer": layer,
        "suite": directory,
        "status": "pass" if completed.returncode == 0 else "fail",
        "has_skips": "skipped" in output.lower(),
        "output": output.strip(),
    }


def main() -> int:
    results = [run_layer(layer, directory) for layer, directory in LAYERS.items()]
    layer_pass = {int(item["layer"]): item["status"] == "pass" for item in results}

    sdk_layers = {
        "rust": {
            0: layer_pass[0],
            1: layer_pass[1],
            2: layer_pass[2],
            3: layer_pass[3],
            4: False,
        },
        "python": {0: layer_pass[0], 1: layer_pass[1], 2: False, 3: False, 4: False},
        "typescript": {
            0: layer_pass[0],
            1: False,
            2: False,
            3: False,
            4: False,
        },
        "go": {
            0: layer_pass[0],
            1: shutil.which("go") is not None and layer_pass[1],
            2: False,
            3: False,
            4: False,
        },
        "java": {0: layer_pass[0], 1: False, 2: False, 3: False, 4: False},
    }
    certifications = [
        certification_for(sdk, layers).__dict__ for sdk, layers in sdk_layers.items()
    ]
    report = {
        "framework_version": "0.1",
        "abi_version": "reason-ir/0.1",
        "generated_on": date.today().isoformat(),
        "layers": results,
        "certifications": certifications,
        "notes": [
            "Layer 4 compares Rust, Python, and TypeScript in this environment.",
            "Go remains unverified when the Go toolchain is unavailable.",
            "Java DTO declarations compile, but a JSON codec adapter is not implemented.",
            "Full Compatible certification requires all five SDKs to pass Layer 4.",
        ],
    }

    reports = ROOT / "conformance" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "conformance_results_v0.1.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Conformance Report v0.1",
        "",
        f"Generated: {report['generated_on']}",
        "",
        f"ABI: `{report['abi_version']}`",
        "",
        "## Layer Results",
        "",
        "| Layer | Suite | Result | Notes |",
        "|---|---|---|---|",
    ]
    for item in results:
        notes = "contains skipped toolchains" if item["has_skips"] else ""
        lines.append(
            f"| {item['layer']} | `{item['suite']}` | {str(item['status']).upper()} | {notes} |"
        )
    lines += [
        "",
        "## SDK Certification",
        "",
        "| SDK | Level | Certification |",
        "|---|---:|---|",
    ]
    for item in certifications:
        lines.append(f"| {item['sdk']} | {item['level']} | {item['label']} |")
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {note}" for note in report["notes"])
    lines += [
        "",
        "The framework is complete, but Full Compatible certification is withheld",
        "until Go and Java provide executable DTO codecs and all five SDKs pass",
        "the same Layer 4 fixture run.",
        "",
    ]
    (reports / "Conformance_Report_v0.1.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    for item in results:
        print(f"Layer {item['layer']}: {str(item['status']).upper()}")
    return 0 if all(layer_pass.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
