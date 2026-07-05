from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from playground.backend.main import SourceRequest, analyze_endpoint


REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "scripts" / "dev.py"
VALID = REPO_ROOT / "examples" / "v0_5" / "002_single_calculation.rsn"


def test_cli_analyze_is_structurally_compatible_with_backend_analyze() -> None:
    source = VALID.read_text(encoding="utf-8")
    backend = analyze_endpoint(SourceRequest(source=source, filename=str(VALID), compiler_mode="normal"))
    result = subprocess.run(
        [sys.executable, str(DEV), "reason", "analyze", str(VALID), "--json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] == backend["ok"]
    assert payload["project_state"]["pipeline"]["stages"] == backend["pipeline"]["stages"]
    assert payload["artifacts"]["reason_ir"] == backend["artifacts"]["reason_ir"]
    assert payload["artifacts"]["execution_plan"] == backend["artifacts"]["execution_plan"]
    assert payload["artifacts"]["simulation"] == backend["artifacts"]["simulation"]

