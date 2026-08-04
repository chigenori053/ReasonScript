from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "scripts" / "dev.py"
VALID = REPO_ROOT / "examples" / "v0_5" / "002_single_calculation.rsn"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_dev_py_exposes_reason_command_group() -> None:
    source = DEV.read_text(encoding="utf-8")
    assert "def cmd_reason" in source
    assert 'if cmd == "reason"' in source


def test_reason_check_accepts_rsn_file() -> None:
    result = _run("reason", "check", str(VALID))
    assert result.returncode == 0
    assert "ReasonScript check passed" in result.stdout


def test_reason_analyze_accepts_rsn_file() -> None:
    result = _run("reason", "analyze", str(VALID), "--json")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["schema_version"] == "reasonscript-cli-analyze/0.1"
    assert payload["ok"] is True


def test_reason_run_accepts_rsn_file() -> None:
    result = _run("reason", "run", str(VALID), "--json")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["schema_version"] == "reasonscript-cli-run/0.1"
    assert payload["ok"] is True

