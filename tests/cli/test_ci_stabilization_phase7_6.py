from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from toolchain.ci import (
    VALIDATION_RULES,
    ci_report,
    ci_summary,
    run_pipeline,
    write_ci_reports,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REASON = REPO_ROOT / "reason"


def _run_reason(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REASON), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_ci_policy_and_workflow_exist() -> None:
    spec = REPO_ROOT / "AGENTS.md"
    workflow = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    assert spec.is_file()
    assert workflow.is_file()
    assert "CI Stabilization" in spec.read_text(encoding="utf-8")


def test_agents_md_documents_ci_stabilization() -> None:
    text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for required in ("CI Stabilization", "reason ci", "CI-001", "CI-010"):
        assert required in text


def test_run_pipeline_passes_on_repository_root() -> None:
    result = run_pipeline(REPO_ROOT, run_tests=False)

    assert result["schema"] == "reasonscript-ci/1.0"
    assert result["ok"] is True
    assert result["diagnostics"] == []
    assert result["rules"] == list(VALIDATION_RULES)
    phase_ids = [phase["id"] for phase in result["phases"]]
    assert phase_ids == [
        "checkout",
        "environment_setup",
        "workspace",
        "diagnostics",
        "artifacts",
        "golden",
        "agent_protocol",
        "compatibility",
        "tests",
    ]
    assert all(phase["status"] == "PASS" for phase in result["phases"])


def test_ci_report_and_summary_are_deterministic_and_machine_readable(tmp_path: Path) -> None:
    result = run_pipeline(REPO_ROOT, run_tests=False)
    paths = write_ci_reports(tmp_path, result)

    report_payload = json.loads(paths["report"].read_text(encoding="utf-8"))
    summary_payload = json.loads(paths["summary"].read_text(encoding="utf-8"))

    assert report_payload == ci_report(result)
    assert summary_payload == ci_summary(result)
    assert summary_payload["schema"] == "reasonscript-ci-summary/1.0"
    assert summary_payload["status"] == "PASS"
    assert summary_payload["workspace"] is True
    assert summary_payload["diagnostics"] is True
    assert summary_payload["artifacts"] is True
    assert summary_payload["golden"] is True
    assert summary_payload["agent_protocol"] is True


def test_direct_reason_ci_command_is_machine_readable(tmp_path: Path) -> None:
    result = _run_reason("ci", str(REPO_ROOT), "--skip-tests", "--json", "--out", str(tmp_path))

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["schema"] == "reasonscript-ci-report/1.0"
    assert payload["status"] == "PASS"
    assert (tmp_path / "ci_report.json").is_file()
    assert (tmp_path / "ci_summary.json").is_file()
