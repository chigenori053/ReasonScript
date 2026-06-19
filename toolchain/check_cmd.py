"""reason check — validate sources without building runtime artifacts."""

from __future__ import annotations

from pathlib import Path

from .manifest import Manifest, ManifestError
from .pipeline import PipelineError, validate_source


def run(project_root: Path) -> int:
    try:
        Manifest.load(project_root)
    except ManifestError as e:
        print(f"Error:\n\n{e}")
        return 1

    src_dir = project_root / "src"
    if not src_dir.exists():
        print("Error:\n\nSourceDirectoryMissing\n\nsrc/ not found.")
        return 1

    sources = sorted(src_dir.rglob("*.rsn"))
    if not sources:
        print("Error:\n\nNoSourceFiles\n\nNo .rsn files found in src/.")
        return 1

    errors: list[str] = []
    for src_path in sources:
        source = src_path.read_text(encoding="utf-8")
        try:
            validate_source(source, src_path)
        except PipelineError as e:
            errors.append(f"{src_path}: {e.code}: {e.message}")

    if errors:
        for e in errors:
            print(f"Error:\n\n{e}")
        return 1

    print(f"Check passed. {len(sources)} file(s) validated.")
    return 0
