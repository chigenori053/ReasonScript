"""Bounded executable-permission compatibility for installed distributions."""
from __future__ import annotations

import os
from pathlib import Path


_PACKAGED_EXECUTABLES = (
    "bin/reason-runtime",
    "bin/reason-updater",
    "bin/reason-vision",
    "bin/reasonunit-runtime-native",
)


def restore_runtime_executables(root: Path) -> list[str]:
    """Repair executable bits stripped by legacy ZIP update extraction.

    The validation-profile marker limits this compatibility path to a packaged
    distribution. Failures remain visible to doctor/install-validate.
    """
    if os.name == "nt" or not (root / "metadata/validation_profile.json").is_file():
        return []
    restored = []
    for relative in _PACKAGED_EXECUTABLES:
        target = root / relative
        if not target.is_file() or os.access(target, os.X_OK):
            continue
        try:
            target.chmod(target.stat().st_mode | 0o111)
        except OSError:
            continue
        restored.append(relative)
    return restored
