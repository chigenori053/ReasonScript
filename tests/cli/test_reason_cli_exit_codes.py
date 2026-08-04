from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "scripts" / "dev.py"
VALID = REPO_ROOT / "examples" / "v0_5" / "002_single_calculation.rsn"
INVALID = REPO_ROOT / "examples" / "v0_5" / "invalid" / "undefined_dependency.rsn"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_check_returns_zero_for_valid_source() -> None:
    assert _run("reason", "check", str(VALID)).returncode == 0


def test_check_returns_one_for_invalid_source() -> None:
    result = _run("reason", "check", str(INVALID))
    assert result.returncode == 1
    assert "CAL-020" in result.stdout


def test_missing_file_returns_three() -> None:
    assert _run("reason", "check", "examples/v0_5/nope.rsn").returncode == 3


def test_invalid_option_returns_two() -> None:
    assert _run("reason", "check", str(VALID), "--nope").returncode == 2

