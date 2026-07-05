from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REASON = REPO_ROOT / "reason"
DEV = REPO_ROOT / "scripts" / "dev.py"
VALID = REPO_ROOT / "examples" / "v0_5" / "002_single_calculation.rsn"


def _run_reason(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REASON), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_dev_reason(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), "reason", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_agents_md_defines_required_protocol_sections() -> None:
    text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    for required in (
        "Development Workflow",
        "Required Commands",
        "Validation Sequence",
        "Artifact Policy",
        "Golden Policy",
        "Completion Criteria",
        "Reporting Format",
    ):
        assert required in text


def test_direct_reason_exposes_standard_phase7_5_artifact_commands(tmp_path: Path) -> None:
    artifacts = _run_reason("artifacts", str(VALID), "--out", str(tmp_path))
    validation = _run_reason("validate-artifacts", str(tmp_path), "--json")
    manifest = _run_reason("manifest", str(tmp_path), "--json")

    assert artifacts.returncode == 0
    assert validation.returncode == 0
    assert manifest.returncode == 0
    assert json.loads(validation.stdout)["diagnostics"] == []
    assert json.loads(manifest.stdout)["schema"] == "reasonscript-artifact-manifest/1.0"


def test_direct_reason_analyze_matches_standard_command_sequence() -> None:
    check = _run_reason("check", str(VALID), "--json")
    analyze = _run_reason("analyze", str(VALID), "--json")
    run = _run_reason("run", str(VALID), "--json")
    analyze_payload = json.loads(analyze.stdout)
    run_payload = json.loads(run.stdout)

    assert check.returncode == 0
    assert analyze.returncode == 0
    assert run.returncode == 0
    assert analyze_payload["schema_version"] == "reasonscript-cli-analyze/0.1"
    assert analyze_payload["ok"] is True
    assert run_payload["schema_version"] == "reasonscript-cli-run/0.1"
    assert run_payload["ok"] is True


def test_agent_protocol_validation_and_report_are_machine_readable(tmp_path: Path) -> None:
    validation = _run_dev_reason("agent-protocol", "--json")
    report = _run_dev_reason(
        "agent-report",
        "--task",
        "Phase 7.5",
        "--status",
        "VALIDATED",
        "--tests-passed",
        "39",
        "--artifacts-generated",
        "--out",
        str(tmp_path),
        "--json",
    )

    validation_payload = json.loads(validation.stdout)
    report_payload = json.loads(report.stdout)
    report_file = tmp_path / "agent_report.json"
    file_payload = json.loads(report_file.read_text(encoding="utf-8"))
    assert validation.returncode == 0
    assert validation_payload["schema"] == "reasonscript-agent-protocol/1.0"
    assert validation_payload["diagnostics"] == []
    assert validation_payload["rules"] == [
        "AP-001",
        "AP-002",
        "AP-003",
        "AP-004",
        "AP-005",
        "AP-006",
        "AP-007",
        "AP-008",
        "AP-009",
        "AP-010",
    ]
    assert report.returncode == 0
    assert report_payload["version"] == "1.0"
    assert report_payload["task"] == "Phase 7.5"
    assert report_payload["status"] == "VALIDATED"
    assert report_payload["tests_passed"] == 39
    assert report_payload["artifacts_generated"] is True
    assert file_payload == report_payload
