from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.install_update.validation_profile_test_support import (
    materialize_profiles,
    read_declaration,
    write_declaration,
)
from toolchain.install_update.validation_profile import resolve_validation_profile


@pytest.mark.parametrize("unsafe", ["../../external", "/tmp/external"])
def test_r2_tc_009_path_escape_is_rejected_without_reading_external(tmp_path, unsafe) -> None:
    _, current = materialize_profiles(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    (external / "secret").write_text("must-not-be-read", encoding="utf-8")
    declaration = read_declaration(current)
    declaration["fixtures"]["phase1r"]["path"] = unsafe
    write_declaration(current, declaration)
    profile = resolve_validation_profile(current)
    assert profile.fixtures["phase1r"].status == "invalid_type"
    assert "VP-PATH-001" in {item.code for item in profile.diagnostics}


def test_r2_tc_010_symlink_escape_is_rejected(tmp_path) -> None:
    _, current = materialize_profiles(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = current / "escaped-fixture"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("platform does not support test symlinks")
    declaration = read_declaration(current)
    declaration["fixtures"]["phase1r"]["path"] = "escaped-fixture"
    write_declaration(current, declaration)
    profile = resolve_validation_profile(current)
    assert profile.fixtures["phase1r"].status == "invalid_type"
    assert "VP-PATH-003" in {item.code for item in profile.diagnostics}
