from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "scripts" / "dev.py"


def test_reason_examples_validates_v0_5_corpus() -> None:
    result = subprocess.run(
        [sys.executable, str(DEV), "reason", "examples", "--json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["valid_total"] == 10
    assert payload["invalid_total"] == 6
