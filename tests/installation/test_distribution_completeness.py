import hashlib
import json
import os
import shutil
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
    native = subprocess.run([str(home / "bin/reason"), "vision", "verify-native", "--json"], cwd=tmp_path, env={**os.environ, "PYTHONPATH": "", "REASONSCRIPT_HOME": str(home)}, text=True, capture_output=True)
    assert native.returncode == 0, native.stdout + native.stderr
    assert json.loads(native.stdout)["unsafe_blocks"] == 0
    visualization = subprocess.run([str(home / "bin/reason"), "visualization", "verify-native", "--json"], cwd=tmp_path, env={**os.environ, "PYTHONPATH": "", "REASONSCRIPT_HOME": str(home)}, text=True, capture_output=True)
    assert visualization.returncode == 0, visualization.stdout + visualization.stderr
    assert json.loads(visualization.stdout)["profile"] == "reasonscript-semantic-visualization-runtime/0.1"


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
    assert "vision-runtime-v0.1" in ids
    assert "semantic-visualization-runtime-v0.1" in ids
    assert "reasonunit-runtime-v1.0" in ids
    assert (home / "current/VisionRuntime/Cargo.toml").is_file()
    assert (home / "current/NativeReasonUnitRuntime/Cargo.toml").is_file()
    assert (home / "current/VisualizationRuntime/Cargo.toml").is_file()
    assert (home / "current/bin" / ("reason-vision.exe" if os.name == "nt" else "reason-vision")).is_file()
    assert (home / "current/bin" / ("reason-visualization.exe" if os.name == "nt" else "reason-visualization")).is_file()
    reasonunit_binary = home / "current/bin" / (
        "reasonunit-runtime-native.exe"
        if os.name == "nt"
        else "reasonunit-runtime-native"
    )
    assert reasonunit_binary.is_file()
    native_result = subprocess.run(
        [str(reasonunit_binary), "verify-native"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert native_result.returncode == 0
    assert json.loads(native_result.stdout)["unsafe_blocks"] == 0
    for item in manifest["files"]:
        path = home / item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]


def test_project_identifier_normalization():
    assert normalize_project_identifier("inference-validation") == "inference_validation"
    assert normalize_project_identifier("42 demo!") == "project_42_demo"
    assert normalize_project_identifier("!!!") == "reason_project"
    assert normalize_project_identifier("model") == "project_model"


def test_installed_ml_evaluation_external_project(tmp_path):
    home, manifest = _install(tmp_path)
    installed = home / "current"
    evaluation_files = {p.relative_to(installed).as_posix() for p in (installed / "runtime/visualization/evaluation").glob("*.py")}
    source_files = {p.relative_to(ROOT).as_posix() for p in (ROOT / "runtime/visualization/evaluation").glob("*.py")}
    assert evaluation_files == source_files
    manifest_files = {item["path"].split(f"versions/{manifest['reason_version']}/", 1)[-1] for item in manifest["files"]}
    assert source_files <= manifest_files
    env = os.environ.copy(); env.update({"PYTHONPATH": "", "REASONSCRIPT_HOME": str(home)})
    cli = home / "bin/reason"
    result = subprocess.run([str(cli), "install-validate", "--json"], cwd=tmp_path, env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    mlv = [check for check in payload["checks"] if check["id"].startswith("MLV-INSTALL-")]
    assert len(mlv) == 10 and all(check["status"] == "pass" for check in mlv)


def test_installed_vision_language_pipeline_publishes_ruo_tensors(tmp_path):
    home, _ = _install(tmp_path)
    project = tmp_path / "vision-project"
    shutil.copytree(ROOT / "tests/fixtures/vision_language", project)
    env = os.environ.copy(); env.update({"PYTHONPATH": "", "REASONSCRIPT_HOME": str(home)})
    result = subprocess.run(
        [str(home / "bin/reason"), "run", "vision_pipeline.rsn", "--allow-read", "--allow-write", "--json"],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["runtime_result"]["result"]["status"] == "committed"
    assert (project / "output/solar-observation.ruo").is_file()


def test_development_update_package_contains_native_vision_runtime(tmp_path):
    output = tmp_path / "dist"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_update_package.py"), "--out", str(output),
         "--format", "directory", "--package-class", "development", "--allow-dirty", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    package = Path(json.loads(result.stdout)["path"])
    assert (package / "payload/VisionRuntime/Cargo.toml").is_file()
    assert (package / "payload/NativeReasonUnitRuntime/Cargo.toml").is_file()
    assert (package / "payload/VisualizationRuntime/Cargo.toml").is_file()
    assert (package / "payload/bin" / ("reason-vision.exe" if os.name == "nt" else "reason-vision")).is_file()
    assert (package / "payload/bin" / ("reason-visualization.exe" if os.name == "nt" else "reason-visualization")).is_file()
    reasonunit_name = (
        "reasonunit-runtime-native.exe"
        if os.name == "nt"
        else "reasonunit-runtime-native"
    )
    assert (package / "payload/bin" / reasonunit_name).is_file()
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert "vision-runtime-v0.1" in {item["name"] for item in manifest["components"]}
    assert manifest["package_version"] == "0.5.4.6"

    fresh = tmp_path / "fresh-install"
    environment = os.environ.copy()
    environment["PATH"] = ""  # packaged install must not resolve Cargo or rustc
    installed = subprocess.run(
        [sys.executable, str(package / "payload/scripts/install_common.py"), "--prefix", str(fresh),
         "--non-interactive", "--json"],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
    )
    assert installed.returncode in {0, 1}, installed.stdout + installed.stderr
    report = json.loads(installed.stdout)
    assert report["status"] == "success" and report["reason_version"] == "0.5.4.6"
    assert (fresh / "current/bin" / ("reason-vision.exe" if os.name == "nt" else "reason-vision")).is_file()
    assert (fresh / "current/bin" / reasonunit_name).is_file()
