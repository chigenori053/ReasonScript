from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[2]


def test_python_distribution_includes_cli_runtime_dependencies() -> None:
    configuration = tomllib.loads((ROOT / "pyproject.toml").read_text())
    included = configuration["tool"]["setuptools"]["packages"]["find"]["include"]
    package_data = configuration["tool"]["setuptools"]["package-data"]

    assert "conformance*" in included
    assert "sdk*" in included
    assert "schemas/*.json" in package_data["frontend"]
