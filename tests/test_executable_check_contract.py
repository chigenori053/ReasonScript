"""Phase 0 regression coverage for check/build executability parity."""

from __future__ import annotations

from pathlib import Path

from toolchain import build_cmd, check_cmd


def _write_manifest(root: Path) -> None:
    (root / "reason.toml").write_text(
        """[package]
name = "check-contract"
version = "0.1.0"

[runtime]
backend = "RuntimeReal"
""",
        encoding="utf-8",
    )
    (root / "src").mkdir()


def test_default_check_and_build_accept_executable_match(
    tmp_path: Path, capsys
) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "src" / "main.rsn").write_text(
        """module MatchOnly {
  fn Score(value: int) -> int {
    match value {
      1 => return 10
      default => return 0
    }
  }
  calculation Answer {
    result = Score(1)
  }
}
""",
        encoding="utf-8",
    )

    assert check_cmd.run(tmp_path) == 0
    check_output = capsys.readouterr().out
    assert "Check passed" in check_output

    assert build_cmd.run(tmp_path) == 0
    build_output = capsys.readouterr().out
    assert "Build succeeded" in build_output


def test_optional_is_executable_but_surface_only_mode_remains_available(
    tmp_path: Path, capsys
) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "src" / "main.rsn").write_text(
        """module OptionalOnly {
  calculation Answer {
    result = some(1)
  }
}
""",
        encoding="utf-8",
    )

    assert check_cmd.run(tmp_path, surface_only=True) == 0
    output = capsys.readouterr().out
    assert "Surface-only check passed" in output

    assert check_cmd.run(tmp_path) == 0
    assert "Check passed" in capsys.readouterr().out


def test_executable_check_and_build_share_successful_lowering(
    tmp_path: Path, capsys
) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "src" / "main.rsn").write_text(
        """module Executable {
  calculation Answer {
    result = 40 + 2
  }
}
""",
        encoding="utf-8",
    )

    assert check_cmd.run(tmp_path) == 0
    assert "Check passed" in capsys.readouterr().out
    assert build_cmd.run(tmp_path) == 0
    assert "Build succeeded" in capsys.readouterr().out
    assert (tmp_path / "target/computation_ir/package.json").is_file()
