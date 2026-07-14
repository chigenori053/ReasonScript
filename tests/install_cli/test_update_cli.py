from __future__ import annotations

import json
from pathlib import Path

from toolchain.install_update.cli import run
from tests.install_update.test_update_core import installed, package


def test_update_check_json_contract(tmp_path: Path, capsys) -> None:
    root, _ = installed(tmp_path)
    code = run(["--check", "--package", str(package(tmp_path)), "--prefix", str(root), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["schema_version"] == "reasonscript-update-report/1.0"
    assert payload["status"] == "update_available"


def test_update_cli_requires_package(capsys) -> None:
    assert run(["--check", "--json"]) == 2
    assert "--package is required" in capsys.readouterr().err
