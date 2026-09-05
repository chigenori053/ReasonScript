"""Canonical package source discovery shared by project CLI paths."""

from __future__ import annotations

from pathlib import Path

from .manifest import Manifest


class SourceSelectionError(ValueError):
    """A package source selection rule could not be satisfied."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def package_sources(project_root: Path, manifest: Manifest) -> list[Path]:
    """Return the complete source graph with an explicit entry first.

    An explicit ``source.entry`` may be anywhere inside the project root and
    is included even when it is outside ``src``. Legacy manifests without a
    ``[source]`` table retain recursive ``src/**/*.rsn`` discovery.
    """

    src_dir = project_root / "src"
    discovered = set(src_dir.rglob("*.rsn")) if src_dir.is_dir() else set()

    if manifest.source_entry is None:
        if not src_dir.is_dir():
            raise SourceSelectionError("SourceDirectoryMissing", "src/ not found.")
        return sorted(discovered)

    entry_path = (project_root / manifest.source_entry).resolve()
    if not entry_path.is_file():
        raise SourceSelectionError(
            "SourceEntryMissing",
            f"Entry file '{manifest.source_entry}' not found.",
        )

    discovered.add(entry_path)
    return [entry_path, *sorted(discovered - {entry_path})]
