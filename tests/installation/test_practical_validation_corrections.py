import json
import subprocess
import sys
from pathlib import Path

from toolchain.version_validation import validate_version

ROOT = Path(__file__).resolve().parents[2]


def _project_snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
        for path in sorted(root.rglob("*"))
    }


def test_release_metadata_is_consistent():
    payload = validate_version(ROOT)
    assert payload["schema_version"] == "reasonscript-version-validation/1.0"
    assert payload["status"] == "pass"
    assert [item["id"] for item in payload["checks"]] == [
        *(f"VER-{i:03d}" for i in range(1, 10)),
        "VER-011",
        "VER-012",
    ]


def test_release_documentation_drift_is_reported(tmp_path: Path):
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    version_token = version.replace(".", "_")
    for relative in (
        "VERSION",
        "pyproject.toml",
        "metadata/release_manifest.json",
        "README.md",
        "docs/README.md",
        "CHANGELOG.md",
        f"release/RELEASE_NOTES_v{version_token}.md",
    ):
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace(
            f"Current release: **v{version}**",
            "Current release: **v0.0.0**",
        ),
        encoding="utf-8",
    )

    payload = validate_version(tmp_path)
    checks = {item["id"]: item for item in payload["checks"]}
    assert payload["status"] == "fail"
    assert checks["VER-007"] == {
        "id": "VER-007",
        "status": "fail",
        "actual": "0.0.0",
        "expected": version,
    }


def test_hyphenated_project_and_artifact_resolution(tmp_path: Path):
    cli = ROOT / "reason"
    created = subprocess.run([str(cli), "init", "inference-validation"], cwd=tmp_path, text=True, capture_output=True)
    assert created.returncode == 0, created.stderr
    assert "Package identifier: inference_validation" in created.stdout
    project = tmp_path / "inference-validation"
    source = (project / "src/main.rsn").read_text(encoding="utf-8")
    assert "package inference_validation" in source
    generated = subprocess.run([str(cli), "artifacts", "src/main.rsn"], cwd=project, text=True, capture_output=True)
    assert generated.returncode == 0, generated.stderr
    assert (project / "artifacts/artifact_manifest.json").is_file()
    assert str(project / "artifacts") in generated.stdout


def test_explicit_artifact_output_overrides_manifest(tmp_path: Path):
    cli = ROOT / "reason"
    subprocess.run([str(cli), "init", "demo"], cwd=tmp_path, check=True, capture_output=True)
    project = tmp_path / "demo"
    generated = subprocess.run([str(cli), "artifacts", "src/main.rsn", "--out", "build/output"], cwd=project, text=True, capture_output=True)
    assert generated.returncode == 0, generated.stderr
    assert (project / "build/output/artifact_manifest.json").is_file()


def test_version_validate_cli_json():
    result = subprocess.run([str(ROOT / "reason"), "version-validate", "--json"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "pass"


def test_default_and_explicit_minimal_templates_are_identical(tmp_path: Path):
    cli = ROOT / "reason"
    default_root = tmp_path / "default"
    explicit_root = tmp_path / "explicit"
    default_root.mkdir()
    explicit_root.mkdir()
    default = subprocess.run(
        [str(cli), "init", "demo-project"],
        cwd=default_root,
        text=True,
        capture_output=True,
    )
    explicit = subprocess.run(
        [str(cli), "init", "demo-project", "--template", "minimal"],
        cwd=explicit_root,
        text=True,
        capture_output=True,
    )
    assert default.returncode == explicit.returncode == 0

    default_snapshot = _project_snapshot(default_root / "demo-project")
    explicit_snapshot = _project_snapshot(explicit_root / "demo-project")
    assert default_snapshot == explicit_snapshot
    assert "AGENTS.md" not in default_snapshot
    assert "SPECIFICATIONS" not in default_snapshot


def test_agent_template_generates_guidance_and_passes_validation(tmp_path: Path):
    cli = ROOT / "reason"
    created = subprocess.run(
        [str(cli), "init", "agent-project", "--template", "agent"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert created.returncode == 0, created.stderr
    project = tmp_path / "agent-project"

    agents = (project / "AGENTS.md").read_text(encoding="utf-8")
    specification = (project / "SPECIFICATIONS/Project_Specification.md").read_text(
        encoding="utf-8"
    )
    assert "Specification" in agents
    assert "Implementation" in agents
    assert "Validation" in agents
    assert "Artifact verification" in agents
    assert "Golden tests" in agents
    assert "Completion report" in agents
    assert "Status: DRAFT" in specification
    assert "agent-project Project Specification" in specification
    assert "agent_project-project/0.1" in specification
    assert not (project / "agent_report.json").exists()

    for command in (
        [str(cli), "check"],
        [str(cli), "run"],
        [str(cli), "artifacts", "src/main.rsn"],
    ):
        result = subprocess.run(
            command,
            cwd=project,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    validated = subprocess.run(
        [str(cli), "project-validate", "--json"],
        cwd=project,
        text=True,
        capture_output=True,
    )
    assert validated.returncode == 0, validated.stdout + validated.stderr
    assert json.loads(validated.stdout)["status"] == "passed"


def test_unsupported_template_does_not_create_project(tmp_path: Path):
    result = subprocess.run(
        [str(ROOT / "reason"), "init", "invalid-project", "--template", "unknown"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1
    assert "UnsupportedTemplate" in result.stdout
    assert not (tmp_path / "invalid-project").exists()
