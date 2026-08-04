import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_repository_stabilization_deliverables_exist():
    deliverables = [
        "docs/specs/repository_stabilization_v1.md",
        "requirements-dev.txt",
        "docs/reports/playground/playground_repository_stabilization_audit.md",
        "playground/audits/playground_repository_stabilization_matrix.json",
        "tests/repository",
        "tests/ci",
        ".github/workflows",
    ]

    for relative in deliverables:
        assert (ROOT / relative).exists(), relative


def test_pytest_configuration_normalizes_imports():
    config = (ROOT / "pytest.ini").read_text()

    assert "--import-mode=importlib" in config
    assert "pythonpath = ." in config
    assert "norecursedirs" in config


def test_dev_dependencies_are_explicitly_managed():
    requirements = {
        line.strip()
        for line in (ROOT / "requirements-dev.txt").read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

    for package in {"pytest", "jsonschema", "pydantic", "fastapi", "uvicorn"}:
        assert package in requirements


def test_repository_stabilization_matrix_is_consistent():
    matrix = json.loads((ROOT / "playground/audits/playground_repository_stabilization_matrix.json").read_text())

    assert matrix["specification"] == "repository-stabilization/1.0"
    assert matrix["phase"] == "RS-001"
    assert all(item["status"] == "PASS" for item in matrix["coverage"])
    assert {item["id"] for item in matrix["coverage"]} == {
        "RS-001",
        "RS-002",
        "RS-003",
        "RS-004",
        "RS-005",
        "RS-006",
        "RS-007",
        "RS-008",
    }


def test_frozen_language_surface_artifacts_remain_present():
    required = [
        "docs/specs/reasonscript_language_surface_v0_5.md",
        "playground/audits/playground_language_surface_v0_5_matrix.json",
        "tests/compatibility/test_language_surface_v0_5.py",
    ]

    for relative in required:
        assert (ROOT / relative).exists(), relative
