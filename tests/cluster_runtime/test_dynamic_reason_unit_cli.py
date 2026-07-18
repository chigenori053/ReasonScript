import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def invoke(*args: str) -> tuple[int, dict]:
    result = subprocess.run(
        [str(ROOT / "reason"), "cluster", "dynamic", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode, json.loads(result.stdout)


def test_dynamic_test_model_cli():
    code, payload = invoke("test-model", "--scenario", "dynamic-generation", "--workers", "4", "--json")
    assert code == 0
    assert payload["passed"] is True
    assert payload["scenario"] == "DRU-TM-001"


def test_dynamic_worker_equivalence_cli():
    code, payload = invoke("test-model", "--scenario", "worker-count-equivalence", "--workers", "4", "--json")
    assert code == 0
    assert payload["passed"] is True
