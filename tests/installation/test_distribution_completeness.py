import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from toolchain.distribution_validation import COMPONENTS, normalize_project_identifier

ROOT = Path(__file__).resolve().parents[2]


def _install(tmp_path: Path) -> tuple[Path, dict]:
    home = tmp_path / "install"
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts/install_common.py"), "--prefix", str(home), "--non-interactive", "--json"],
        cwd=tmp_path, text=True, capture_output=True,
    )
    assert process.returncode in (0, 1), process.stderr
    return home, json.loads((home / "install_manifest.json").read_text(encoding="utf-8"))


def test_dc_001_to_003_distribution_import_closure(tmp_path):
    home, _ = _install(tmp_path)
    installed = home / "current"
    assert (installed / "playground/backend/main.py").is_file()  # DC-001
    code = "import playground.backend.main, scripts.reason_cli; print(playground.backend.main.__file__)"
    env = os.environ.copy()
    env["PYTHONPATH"] = ""
    result = subprocess.run([sys.executable, "-P", "-c", f"import sys;sys.path.insert(0,{str(installed)!r});{code}"], cwd=tmp_path, env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr  # DC-002/DC-003
    assert str(installed.resolve()) in str(Path(result.stdout.strip()).resolve())
    assert str(ROOT.resolve()) not in result.stdout


def test_dc_004_to_011_installed_project_and_manifest(tmp_path):
    home, manifest = _install(tmp_path)
    cli = home / "bin/reason"
    env = os.environ.copy()
    env.update({"PYTHONPATH": "", "REASONSCRIPT_HOME": str(home)})
    assert subprocess.run([str(cli), "init", "inference-validation"], cwd=tmp_path, env=env, capture_output=True).returncode == 0
    project = tmp_path / "inference-validation"
    manifest_text = (project / "reason.toml").read_text(encoding="utf-8")
    assert 'name = "inference-validation"' in manifest_text
    assert 'identifier = "inference_validation"' in manifest_text
    for args in (["check", "src/main.rsn"], ["run", "src/main.rsn"], ["artifacts", "src/main.rsn"]):
        result = subprocess.run([str(cli), *args], cwd=project, env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
    validation = subprocess.run([str(cli), "install-validate", "--json"], cwd=tmp_path, env=env, text=True, capture_output=True)
    assert validation.returncode == 0, validation.stdout + validation.stderr
    assert json.loads(validation.stdout)["status"] == "pass"
    finalized = json.loads((home / "install_manifest.json").read_text(encoding="utf-8"))
    assert finalized["distribution_validation"]["installed_cli_smoke"] == "pass"
    assert finalized["distribution_validation"]["status"] == "pass"
    ids = {item["id"] for item in manifest["components"]}
    assert {item[0] for item in COMPONENTS} <= ids
    for item in manifest["files"]:
        path = home / item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]


def test_project_identifier_normalization():
    assert normalize_project_identifier("inference-validation") == "inference_validation"
    assert normalize_project_identifier("42 demo!") == "project_42_demo"
    assert normalize_project_identifier("!!!") == "reason_project"
    assert normalize_project_identifier("model") == "project_model"
