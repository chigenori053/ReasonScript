import json
import os
import subprocess
import sys
from pathlib import Path

from toolchain.install_foundation import (
    doctor_payload,
    install_validation_payload,
    version_payload,
)

ROOT = Path(__file__).resolve().parents[2]

def test_version_contract():
    assert version_payload()["schema_version"] == "reasonscript-version/1.0"
    assert version_payload()["install_foundation_version"] == "1.1"

def test_doctor_has_all_required_checks():
    payload = doctor_payload()
    assert [item["id"] for item in payload["checks"]] == [f"DR-{i:03d}" for i in range(1, 25)]

def test_install_validation_contract():
    payload = install_validation_payload()
    assert payload["status"] == "pass"
    # v1.1 includes 20 base, 10 ML-evaluation, and 6 project-validation checks.
    assert len(payload["checks"]) == 36
    assert [item["id"] for item in payload["checks"][-6:]] == [f"IF-PV-{i:03d}" for i in range(1, 7)]
    assert payload["schema_version"] == "reasonscript-install-validation/1.1"

def test_atomic_install_and_manifest(tmp_path):
    home = tmp_path / "home"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/install_common.py"), "--prefix", str(home), "--non-interactive", "--json"], text=True, capture_output=True)
    assert result.returncode in (0, 1), result.stderr
    manifest = json.loads((home / "install_manifest.json").read_text())
    assert manifest["schema_version"] == "reasonscript-install-manifest/1.0"
    assert {item["id"] for item in manifest["components"]} >= {"standard-library", "playground-backend"}
    assert (home / "current" / "playground" / "backend" / "main.py").is_file()
    assert (home / "current" / "reason").is_file()
    state = json.loads((home / "metadata/install_state.json").read_text())
    assert state["schema_version"] == "reasonscript-install-state/1.1"
    assert state["install_foundation_version"] == "1.1"
    dry = subprocess.run([sys.executable, str(ROOT / "scripts/uninstall.py"), "--prefix", str(home), "--dry-run", "--json"], text=True, capture_output=True)
    assert dry.returncode == 0
    assert (home / "current" / "reason").is_file()
