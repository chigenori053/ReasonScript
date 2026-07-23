"""Resolve packaged and development native ReasonUnit Runtime executables."""

from __future__ import annotations

import os
from pathlib import Path


def native_reasonunit_runtime_name() -> str:
    return "reasonunit-runtime-native.exe" if os.name == "nt" else "reasonunit-runtime-native"


def native_reasonunit_runtime_candidates(root: Path | None = None) -> tuple[Path, ...]:
    distribution_root = (
        root.resolve()
        if root is not None
        else Path(__file__).resolve().parents[1]
    )
    name = native_reasonunit_runtime_name()
    return (
        distribution_root / "bin" / name,
        distribution_root / "NativeReasonUnitRuntime" / "target" / "release" / name,
        distribution_root / "NativeReasonUnitRuntime" / "target" / "debug" / name,
    )


def resolve_native_reasonunit_runtime(root: Path | None = None) -> Path:
    for candidate in native_reasonunit_runtime_candidates(root):
        if candidate.is_file():
            return candidate
    searched = ", ".join(
        str(candidate) for candidate in native_reasonunit_runtime_candidates(root)
    )
    raise FileNotFoundError(
        "RUO-N1-029 native ReasonUnit Runtime executable is missing; "
        f"searched: {searched}"
    )
