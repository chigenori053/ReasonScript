"""reason migrate extensions — safe and deterministic migration from legacy extensions to .rsn."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from toolchain.diagnostics import diagnostic_from_parts

# Supported legacy ReasonScript source extensions that should be migrated to .rsn
LEGACY_EXTENSIONS: tuple[str, ...] = (
    ".re",
    ".rei",
    ".res",
    ".resi",
    ".reason",
    ".rscript",
)

IGNORED_DIRECTORIES: set[str] = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "target",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


@dataclass(frozen=True)
class MigrationItem:
    source: Path
    target: Path
    relative_source: str
    relative_target: str


@dataclass(frozen=True)
class MigrationConflict:
    source: Path
    target: Path
    relative_source: str
    relative_target: str
    reason: str
    diagnostic_code: str


def run(args: list[str], current_working_dir: Path | None = None) -> int:
    """Entry point for `reason migrate extensions [options] [path]`."""
    root = current_working_dir or Path.cwd()

    check_mode = "--check" in args or "--dry-run" in args
    json_mode = "--json" in args

    # Filter out options to find path argument
    positional_args = [arg for arg in args if not arg.startswith("-")]
    target_path = root
    if positional_args:
        target_path = (root / positional_args[0]).resolve()
    elif "--path" in args:
        idx = args.index("--path")
        if idx + 1 < len(args):
            target_path = (root / args[idx + 1]).resolve()
        else:
            if json_mode:
                print(json.dumps({
                    "command": "migrate extensions",
                    "status": "failure",
                    "diagnostics": [_diag_dict("CLI-0002", "Missing argument for --path flag.", file="")]
                }, indent=2))
            else:
                print("Error:\n\nCLI-0002\n\nMissing argument for --path flag.")
            return 1

    if not target_path.exists():
        msg = f"Target path '{target_path}' does not exist."
        if json_mode:
            print(json.dumps({
                "command": "migrate extensions",
                "status": "failure",
                "diagnostics": [_diag_dict("CLI-0003", msg, file=str(target_path))]
            }, indent=2))
        else:
            print(f"Error:\n\nCLI-0003\n\n{msg}")
        return 1

    try:
        return _execute_migration(target_path, check_mode=check_mode, json_mode=json_mode)
    except OSError as error:
        msg = f"File system error during migration: {error}"
        if json_mode:
            print(json.dumps({
                "command": "migrate extensions",
                "status": "failure",
                "diagnostics": [_diag_dict("CLI-0003", msg, file=str(target_path))]
            }, indent=2))
        else:
            print(f"Error:\n\nCLI-0003\n\n{msg}")
        return 2


def discover_legacy_files(target_path: Path) -> list[Path]:
    """Deterministically find all files matching legacy source extensions."""
    if target_path.is_file():
        if target_path.suffix.lower() in LEGACY_EXTENSIONS:
            return [target_path]
        return []

    discovered: list[Path] = []
    for root_dir, dirs, files in os.walk(target_path):
        # Prune ignored directories
        dirs[:] = sorted([d for d in dirs if d not in IGNORED_DIRECTORIES and not d.startswith(".")])
        for file_name in sorted(files):
            file_path = Path(root_dir) / file_name
            if file_path.suffix.lower() in LEGACY_EXTENSIONS:
                discovered.append(file_path)

    return sorted(discovered)


def plan_migrations(
    root: Path, legacy_files: list[Path]
) -> tuple[list[MigrationItem], list[MigrationConflict]]:
    """Generate migration plan and detect conflicts."""
    items: list[MigrationItem] = []
    conflicts: list[MigrationConflict] = []

    # Map of lowercase target path -> list of sources targeting it
    target_targets_map: dict[str, list[tuple[Path, Path]]] = {}

    for src in legacy_files:
        rel_src = _format_relpath(src, root)
        # Check if source is a symlink
        if src.is_symlink():
            conflicts.append(MigrationConflict(
                source=src,
                target=src.with_suffix(".rsn"),
                relative_source=rel_src,
                relative_target=_format_relpath(src.with_suffix(".rsn"), root),
                reason="Source is a symlink; symlinks cannot be safely migrated.",
                diagnostic_code="SRC-0005",
            ))
            continue

        target = src.with_suffix(".rsn")
        rel_target = _format_relpath(target, root)

        # Check if target already exists on filesystem
        if target.exists():
            conflicts.append(MigrationConflict(
                source=src,
                target=target,
                relative_source=rel_src,
                relative_target=rel_target,
                reason=f"Target file '{rel_target}' already exists on disk.",
                diagnostic_code="SRC-0004",
            ))
            continue

        item = MigrationItem(
            source=src,
            target=target,
            relative_source=rel_src,
            relative_target=rel_target,
        )
        items.append(item)

        norm_key = str(target.resolve()).lower()
        if norm_key not in target_targets_map:
            target_targets_map[norm_key] = []
        target_targets_map[norm_key].append((src, target))

    # Detect many-to-one conflicts or case-insensitive target collisions
    for norm_key, sources in target_targets_map.items():
        if len(sources) > 1:
            for src, target in sources:
                rel_src = _format_relpath(src, root)
                rel_target = _format_relpath(target, root)
                conflicts.append(MigrationConflict(
                    source=src,
                    target=target,
                    relative_source=rel_src,
                    relative_target=rel_target,
                    reason=f"Multiple legacy files map to the same destination '{rel_target}'.",
                    diagnostic_code="SRC-0004",
                ))
            # Remove from items
            conflicted_sources = {src for src, _ in sources}
            items = [item for item in items if item.source not in conflicted_sources]

    return sorted(items, key=lambda i: i.relative_source), sorted(conflicts, key=lambda c: c.relative_source)


def _execute_migration(target_path: Path, *, check_mode: bool, json_mode: bool) -> int:
    root = target_path if target_path.is_dir() else target_path.parent
    legacy_files = discover_legacy_files(target_path)
    items, conflicts = plan_migrations(root, legacy_files)

    manifest_path = root / "reason.toml"
    has_manifest = manifest_path.is_file()
    manifest_updates: list[tuple[str, str]] = []

    if has_manifest:
        try:
            content = manifest_path.read_text(encoding="utf-8")
            for ext in LEGACY_EXTENSIONS:
                pattern = re.compile(rf'(\b[\w./\\-]+\b){re.escape(ext)}\b')
                for match in pattern.finditer(content):
                    old_ref = match.group(0)
                    new_ref = old_ref[:-len(ext)] + ".rsn"
                    manifest_updates.append((old_ref, new_ref))
        except OSError:
            pass

    diagnostics: list[dict[str, Any]] = []
    for conflict in conflicts:
        diagnostics.append(_diag_dict(
            conflict.diagnostic_code,
            conflict.reason,
            file=conflict.relative_source,
        ))

    if conflicts:
        if json_mode:
            print(json.dumps({
                "command": "migrate extensions",
                "status": "failure",
                "check_mode": check_mode,
                "root": str(root),
                "scanned_files": len(legacy_files),
                "planned_migrations": [
                    {"from": i.relative_source, "to": i.relative_target} for i in items
                ],
                "conflicts": [
                    {
                        "source": c.relative_source,
                        "target": c.relative_target,
                        "reason": c.reason,
                        "code": c.diagnostic_code,
                    }
                    for c in conflicts
                ],
                "manifest_updates": [
                    {"from": old, "to": new} for old, new in manifest_updates
                ],
                "diagnostics": diagnostics,
            }, indent=2))
        else:
            mode_str = "Check (Dry Run)" if check_mode else "Execute"
            print(f"ReasonScript Migration: Extensions to .rsn\nMode: {mode_str}\nTarget: {root}\n")
            print(f"Error: {len(conflicts)} migration conflict(s) detected:\n")
            for c in conflicts:
                print(f"  - [{c.diagnostic_code}] {c.relative_source} -> {c.relative_target}")
                print(f"    Reason: {c.reason}")
            print("\nMigration aborted. No files were modified.")
        return 1

    if check_mode:
        if json_mode:
            print(json.dumps({
                "command": "migrate extensions",
                "status": "success",
                "check_mode": True,
                "root": str(root),
                "scanned_files": len(legacy_files),
                "planned_migrations": [
                    {"from": i.relative_source, "to": i.relative_target} for i in items
                ],
                "conflicts": [],
                "manifest_updates": [
                    {"from": old, "to": new} for old, new in manifest_updates
                ],
                "diagnostics": [],
            }, indent=2))
        else:
            print(f"ReasonScript Migration: Extensions to .rsn\nMode: Check (Dry Run)\nTarget: {root}\n")
            if not items and not manifest_updates:
                print("No legacy source files or references found. Migration not needed.")
            else:
                print(f"Found {len(items)} file(s) to migrate:")
                for item in items:
                    print(f"  - {item.relative_source} -> {item.relative_target}")
                if manifest_updates:
                    print("\nManifest updates (reason.toml):")
                    for old, new in manifest_updates:
                        print(f"  - {old} -> {new}")
                print("\nCheck passed: 0 conflicts detected. Run without --check to apply migrations.")
        return 0

    # Execute migration with rollback protection
    completed_renames: list[tuple[Path, Path]] = []
    original_manifest_content: str | None = None

    try:
        # Perform renames
        for item in items:
            item.source.rename(item.target)
            completed_renames.append((item.source, item.target))

        # Update manifest if needed
        if has_manifest and manifest_updates:
            original_manifest_content = manifest_path.read_text(encoding="utf-8")
            updated_content = original_manifest_content
            for old_ref, new_ref in manifest_updates:
                updated_content = updated_content.replace(old_ref, new_ref)
            manifest_path.write_text(updated_content, encoding="utf-8")

    except Exception as error:
        # Rollback all completed renames in reverse order
        rollback_failures = 0
        for original_source, renamed_target in reversed(completed_renames):
            try:
                if renamed_target.exists():
                    renamed_target.rename(original_source)
            except OSError:
                rollback_failures += 1

        if original_manifest_content is not None and has_manifest:
            try:
                manifest_path.write_text(original_manifest_content, encoding="utf-8")
            except OSError:
                rollback_failures += 1

        rollback_status = "Rollback successful." if rollback_failures == 0 else f"Rollback partially failed ({rollback_failures} errors)."
        err_msg = f"Migration failed during rename: {error}. {rollback_status}"

        if json_mode:
            print(json.dumps({
                "command": "migrate extensions",
                "status": "failure",
                "check_mode": False,
                "root": str(root),
                "diagnostics": [_diag_dict("CLI-0003", err_msg, file=str(root))],
            }, indent=2))
        else:
            print(f"Error:\n\nCLI-0003\n\n{err_msg}")
        return 2

    # Success output
    if json_mode:
        print(json.dumps({
            "command": "migrate extensions",
            "status": "success",
            "check_mode": False,
            "root": str(root),
            "scanned_files": len(legacy_files),
            "migrated_files": [
                {"from": i.relative_source, "to": i.relative_target} for i in items
            ],
            "conflicts": [],
            "manifest_updated": bool(has_manifest and manifest_updates),
            "diagnostics": [],
        }, indent=2))
    else:
        print(f"ReasonScript Migration: Extensions to .rsn\nMode: Execute\nTarget: {root}\n")
        if not items and not manifest_updates:
            print("No legacy source files or references found. Nothing to migrate.")
        else:
            print(f"Successfully migrated {len(items)} file(s):")
            for item in items:
                print(f"  - {item.relative_source} -> {item.relative_target}")
            if has_manifest and manifest_updates:
                print("\nUpdated reason.toml references:")
                for old, new in manifest_updates:
                    print(f"  - {old} -> {new}")
            print("\nMigration completed successfully.")

    return 0


def _format_relpath(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _diag_dict(code: str, message: str, *, file: str) -> dict[str, Any]:
    diag = diagnostic_from_parts(
        code=code,
        message=message,
        file=file,
    )
    res = asdict(diag)
    # Ensure id is populated for contract
    if not res.get("id"):
        res["id"] = f"diag-migrate-{code.lower()}"
    return res
