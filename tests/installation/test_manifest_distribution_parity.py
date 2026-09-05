"""Source-tree and isolated installed-CLI Manifest contract parity."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run(cli: Path, args: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(cli), *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_legacy_project(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "reason.toml").write_text(
        """[package]
name = "legacy-parity"
version = "0.1.0"

[runtime]
backend = "RuntimeReal"
""",
        encoding="utf-8",
    )
    (root / "src/model.rsn").write_text(
        """module Model {
  calculation Value {
    result = 42
  }
}
""",
        encoding="utf-8",
    )


def test_source_and_isolated_install_manifest_parity(tmp_path: Path) -> None:
    install_root = tmp_path / "install"
    installed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/install_common.py"),
            "--prefix",
            str(install_root),
            "--non-interactive",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode in (0, 1), installed.stdout + installed.stderr

    # The platform wrappers differ (``reason`` vs ``reason.cmd``), while the
    # generated launcher is the shared installed-CLI entry on every target.
    installed_cli = install_root / "bin/reason-launcher.py"
    assert installed_cli.is_file()
    source_project = tmp_path / "source-project"
    installed_project = tmp_path / "installed-project"
    _write_legacy_project(source_project)
    _write_legacy_project(installed_project)

    source_env = dict(os.environ)
    source_env["PYTHONPATH"] = str(ROOT)
    installed_env = dict(os.environ)
    installed_env.update(
        {
            "PYTHONPATH": "",
            "REASONSCRIPT_HOME": str(install_root),
        }
    )

    source_check = _run(ROOT / "reason", ["check"], source_project, source_env)
    installed_check = _run(installed_cli, ["check"], installed_project, installed_env)
    assert source_check.returncode == installed_check.returncode == 0
    assert source_check.stdout == installed_check.stdout
    assert source_check.stderr == installed_check.stderr == ""

    source_build = _run(ROOT / "reason", ["build"], source_project, source_env)
    installed_build = _run(installed_cli, ["build"], installed_project, installed_env)
    assert source_build.returncode == installed_build.returncode == 0
    assert source_build.stdout == installed_build.stdout
    assert source_build.stderr == installed_build.stderr == ""

    source_run = _run(ROOT / "reason", ["run"], source_project, source_env)
    installed_run = _run(installed_cli, ["run"], installed_project, installed_env)
    assert source_run.returncode == installed_run.returncode == 0
    assert source_run.stdout == installed_run.stdout
    assert source_run.stderr == installed_run.stderr == ""

    source_parent = tmp_path / "source-init"
    installed_parent = tmp_path / "installed-init"
    source_parent.mkdir()
    installed_parent.mkdir()
    source_init = _run(ROOT / "reason", ["init", "standard-project"], source_parent, source_env)
    installed_init = _run(
        installed_cli,
        ["init", "standard-project"],
        installed_parent,
        installed_env,
    )
    assert source_init.returncode == installed_init.returncode == 0
    assert source_init.stdout == installed_init.stdout
    assert source_init.stderr == installed_init.stderr == ""

    for command in (["build"], ["run"]):
        source_result = _run(
            ROOT / "reason",
            command,
            source_parent / "standard-project",
            source_env,
        )
        installed_result = _run(
            installed_cli,
            command,
            installed_parent / "standard-project",
            installed_env,
        )
        assert source_result.returncode == installed_result.returncode == 0
        assert source_result.stdout == installed_result.stdout
        assert source_result.stderr == installed_result.stderr == ""
