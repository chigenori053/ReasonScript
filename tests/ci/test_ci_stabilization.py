from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text()


def test_required_workflows_exist():
    for name in {"lint.yml", "build.yml", "test.yml", "release.yml"}:
        assert (WORKFLOWS / name).exists(), name


def test_workflows_install_shared_dev_requirements():
    for name in {"lint.yml", "build.yml", "test.yml", "release.yml"}:
        content = _workflow(name)
        assert "python3 -m pip install --upgrade pip" in content
        assert "python3 -m pip install -r requirements-dev.txt" in content


def test_workflows_use_test_platform_entrypoint():
    assert "scripts/test_platform.py lint" in _workflow("lint.yml")
    assert "scripts/test_platform.py build --quick" in _workflow("build.yml")
    assert "scripts/test_platform.py test" in _workflow("test.yml")
    assert "scripts/test_platform.py regression" in _workflow("test.yml")
    assert "scripts/test_platform.py release-check --quick" in _workflow("release.yml")


def test_v0_6_language_layer_validation_scope_is_in_standard_test_platform():
    test_platform = (ROOT / "scripts" / "test_platform.py").read_text()

    for required_path in [
        "tests/compatibility",
        "language_surface_ast_mapping_tests",
        "tests/playground",
    ]:
        assert required_path in test_platform

    assert (ROOT / "tests/compatibility/test_module_model_equivalence.py").exists()
    assert (ROOT / "tests/playground/test_artifact_contract_v0_6.py").exists()
    assert (ROOT / "tests/compatibility/test_projection_core_non_regression.py").exists()
    assert (ROOT / "tests/playground/test_projection_summary_v0_6.py").exists()
    assert (ROOT / "tests/playground/test_diagnostics_view_v0_6.py").exists()
    assert (ROOT / "tests/compatibility/test_top_level_construct_policy_v0_6.py").exists()
    assert (ROOT / "tests/playground/test_top_level_construct_projection_v0_6.py").exists()
    assert (ROOT / "tests/playground/test_reserved_construct_diagnostics_v0_6.py").exists()
