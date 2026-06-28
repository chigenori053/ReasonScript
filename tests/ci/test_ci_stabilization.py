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
