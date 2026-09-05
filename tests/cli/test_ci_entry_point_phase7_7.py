from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from toolchain.ci_entry import VALIDATION_RULES, validate_entry_point

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


def test_ci_entry_policy_exists() -> None:
    spec = REPO_ROOT / "AGENTS.md"
    assert spec.is_file()
    assert "Canonical CI Entry Point" in spec.read_text(encoding="utf-8")


def test_agents_md_documents_canonical_entry_point() -> None:
    text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for required in ("Canonical CI Entry Point", "Coding Agent Policy", "reason ci", "CE-001", "CE-005"):
        assert required in text


def test_validate_entry_point_passes_on_repository_root() -> None:
    result = validate_entry_point(REPO_ROOT)

    assert result["schema"] == "reasonscript-ci-entry/1.0"
    assert result["ok"] is True
    assert result["diagnostics"] == []
    assert result["rules"] == list(VALIDATION_RULES)


def test_direct_reason_ci_entry_command_is_machine_readable() -> None:
    result = _run_reason("ci-entry", str(REPO_ROOT), "--json")

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["schema"] == "reasonscript-ci-entry/1.0"
    assert payload["ok"] is True
    assert payload["diagnostics"] == []
