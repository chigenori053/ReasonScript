"""Consistent package source discovery for the toolchain commands."""

from __future__ import annotations

from pathlib import Path

from .manifest import Manifest


class SourceSelectionError(ValueError):
    """A manifest-selected source cannot be used."""

    code = "SourceEntryMissing"


def package_sources(project_root: Path, manifest: Manifest) -> list[Path]:
    """Return the complete module graph after validating an explicit entry.

    ``source.entry`` identifies the canonical package entry point, but does
    not restrict module discovery: imported sibling modules remain part of
    the package graph. Legacy manifests without ``[source]`` retain their
    historical recursive ``src/**/*.rsn`` behavior.
    """

    src_dir = project_root / "src"
    if not src_dir.is_dir():
        return []

    if manifest.source_entry is not None:
        entry = Path(manifest.source_entry)
        if entry.is_absolute() or ".." in entry.parts:
            raise SourceSelectionError(
                f"source entry '{manifest.source_entry}' is outside the project"
            )
        entry_path = (project_root / entry).resolve()
        try:
            entry_path.relative_to(project_root.resolve())
        except ValueError as error:
            raise SourceSelectionError(
                f"source entry '{manifest.source_entry}' is outside the project"
            ) from error
        if not entry_path.is_file():
            raise SourceSelectionError(
                f"source entry '{manifest.source_entry}' does not exist"
            )

    return sorted(src_dir.rglob("*.rsn"))
