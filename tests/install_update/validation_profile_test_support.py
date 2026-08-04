from __future__ import annotations

import json
import shutil
from pathlib import Path

from tests.install_update.rollback_legacy_support import (
    INSTALLED_FIXTURE,
    PACKAGE_FIXTURE,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PHASE_R2_ARTIFACTS = REPOSITORY_ROOT / "artifacts/install_foundation_v1_1_1/phase_r2"


def materialize_profiles(tmp_path: Path) -> tuple[Path, Path]:
    installed = tmp_path / "installed"
    current = tmp_path / "release_0_5_1"
    shutil.copytree(INSTALLED_FIXTURE, installed)
    shutil.copytree(PACKAGE_FIXTURE / "payload", current)
    return installed / "versions/0.5.0", current


def declaration_path(release: Path) -> Path:
    return release / "metadata/validation_profile.json"


def read_declaration(release: Path) -> dict:
    return json.loads(declaration_path(release).read_text(encoding="utf-8"))


def write_declaration(release: Path, value: dict) -> None:
    declaration_path(release).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
