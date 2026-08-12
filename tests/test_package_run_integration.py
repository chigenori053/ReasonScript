"""Stable package execution must use the same integrated runtime as the API."""

from __future__ import annotations

import json
from pathlib import Path

from toolchain.run_cmd import run


def _project(root: Path) -> None:
    (root / "src").mkdir()
    (root / "reason.toml").write_text(
        """[package]
name = "cross-run"
version = "0.1.0"

[runtime]
backend = "RuntimeReal"
""",
        encoding="utf-8",
    )
    (root / "src" / "model.rsn").write_text(
        """package crossrun
pub module model {
  pub fn Score(value: int) -> int {
    return value * 2
  }
}
""",
        encoding="utf-8",
    )
    (root / "src" / "train.rsn").write_text(
        """module Train {
            import crossrun.model
            calculation Main {
    result = model::Score(21)
  }
}
""",
        encoding="utf-8",
    )


def test_reason_run_executes_cross_module_package_and_returns_runtime_json(
    tmp_path: Path, capsys
) -> None:
    _project(tmp_path)

    assert run(tmp_path, entry="Train::Main", include_trace=True) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "success"
    assert result["entry"] == "Train::Main"
    assert result["runtime_result"]["result"] == 42
    assert result["runtime_result"]["calculations"] == {"Main": 42}
    assert result["trace"] == []


def test_reason_run_rejects_unknown_package_entry(tmp_path: Path, capsys) -> None:
    _project(tmp_path)

    assert run(tmp_path, entry="Train::Missing") == 1

    assert "UnknownEntry" in capsys.readouterr().out


def test_reason_run_materializes_large_result_as_external_artifact(
    tmp_path: Path, capsys
) -> None:
    _project(tmp_path)
    (tmp_path / "src" / "train.rsn").write_text(
        """module Train {
  calculation Main {
    result = tensor.random_uniform([257], seed = 9)
  }
}
""",
        encoding="utf-8",
    )

    assert run(tmp_path, entry="Main") == 0

    result = json.loads(capsys.readouterr().out)["runtime_result"]["result"]
    assert result["value_kind"] == "external"
    assert Path(result["storage_ref"]).is_file()
    assert result["checksum"].startswith("sha256:")
