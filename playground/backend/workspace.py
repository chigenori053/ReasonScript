"""ReasonScript Playground IDE — Phase 3 workspace file contract.

Implements the workspace scan / read / save / path-safety rules defined in
docs/development/workspace_contract.md and
docs/development/file_operation_contract.md. Pure Python/pathlib, no FastAPI
dependency, so it can be unit tested by calling functions directly.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

MAX_DEPTH = 8
MAX_FILES = 5000

IGNORED_DIRS = {".git", "node_modules", "target", "dist", "build"}

SOURCE_EXTENSIONS = {".rsn", ".reason"}


class WorkspacePathError(Exception):
    """Raised for invalid workspace roots or paths that escape the workspace root."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _error(code: str, message: str) -> dict[str, Any]:
    return {"code": code, "message": message}


def resolve_workspace_root(raw: str) -> Path:
    """Resolve and validate a user-supplied workspace root path."""
    if not raw:
        raise WorkspacePathError("INVALID_ROOT", "workspace_root is required")
    root = Path(raw).expanduser().resolve()
    if not root.exists():
        raise WorkspacePathError("NOT_FOUND", f"workspace root not found: {raw}")
    if not root.is_dir():
        raise WorkspacePathError("NOT_A_DIRECTORY", f"workspace root is not a directory: {raw}")
    return root


def resolve_within_workspace(root: Path, relative_path: str) -> Path:
    """Resolve relative_path against root, rejecting any path that escapes root.

    Works for save targets that do not exist yet — Path.resolve() does not
    require the target to exist.
    """
    if not relative_path:
        raise WorkspacePathError("INVALID_PATH", "relative_path is required")
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise WorkspacePathError(
            "PATH_TRAVERSAL", f"path escapes workspace root: {relative_path}"
        ) from exc
    return candidate


def _is_source_file(name: str) -> bool:
    return Path(name).suffix in SOURCE_EXTENSIONS


def _scan_dir(
    root: Path,
    directory: Path,
    depth: int,
    counters: dict[str, int],
    truncated: dict[str, bool],
) -> list[dict[str, Any]]:
    if depth > MAX_DEPTH or truncated["value"]:
        return []

    try:
        entries = list(os.scandir(directory))
    except OSError:
        return []

    def sort_key(entry: os.DirEntry) -> tuple[int, str]:
        is_dir = entry.is_dir(follow_symlinks=False)
        return (0 if is_dir else 1, entry.name.lower())

    entries.sort(key=sort_key)

    nodes: list[dict[str, Any]] = []
    for entry in entries:
        if truncated["value"]:
            break

        name = entry.name
        path = Path(entry.path)
        is_dir = entry.is_dir(follow_symlinks=False)
        is_ignored = is_dir and name in IGNORED_DIRS
        relative_path = str(path.relative_to(root))

        if is_dir:
            if is_ignored:
                nodes.append({
                    "name": name,
                    "relative_path": relative_path,
                    "kind": "directory",
                    "extension": None,
                    "is_ignored": True,
                    "is_source": False,
                    "children": [],
                })
                continue

            children = _scan_dir(root, path, depth + 1, counters, truncated)
            nodes.append({
                "name": name,
                "relative_path": relative_path,
                "kind": "directory",
                "extension": None,
                "is_ignored": False,
                "is_source": False,
                "children": children,
            })
        else:
            counters["file_count"] += 1
            if counters["file_count"] >= MAX_FILES:
                truncated["value"] = True
            nodes.append({
                "name": name,
                "relative_path": relative_path,
                "kind": "file",
                "extension": path.suffix.lstrip(".") or None,
                "is_ignored": False,
                "is_source": _is_source_file(name),
                "children": [],
            })

    return nodes


def scan_workspace(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Recursively scan a workspace root, respecting ignore/depth/file-count rules."""
    counters = {"file_count": 0}
    truncated = {"value": False}
    files = _scan_dir(root, root, 0, counters, truncated)
    scan_status = {
        "status": "truncated" if truncated["value"] else "success",
        "truncated": truncated["value"],
        "max_depth": MAX_DEPTH,
        "max_files": MAX_FILES,
        "file_count": counters["file_count"],
    }
    return files, scan_status


def read_workspace_file(root: Path, relative_path: str) -> dict[str, Any]:
    """Read a workspace file's contents. Returns an ok/error response dict."""
    try:
        target = resolve_within_workspace(root, relative_path)
    except WorkspacePathError as exc:
        return {"ok": False, "relative_path": relative_path, "error": _error(exc.code, exc.message)}

    if not target.exists():
        return {"ok": False, "relative_path": relative_path, "error": _error("NOT_FOUND", "file not found")}
    if not target.is_file():
        return {"ok": False, "relative_path": relative_path, "error": _error("NOT_A_FILE", "path is not a file")}

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"ok": False, "relative_path": relative_path, "error": _error("DECODE_ERROR", "file is not valid UTF-8 text")}

    stat = target.stat()
    return {
        "ok": True,
        "relative_path": relative_path,
        "content": content,
        "version": str(stat.st_mtime),
        "read_only": not os.access(target, os.W_OK),
    }


def save_workspace_file(
    root: Path,
    relative_path: str,
    content: str,
    expected_version: str | None = None,
) -> dict[str, Any]:
    """Write content to a workspace file. Returns an ok/error response dict."""
    try:
        target = resolve_within_workspace(root, relative_path)
    except WorkspacePathError as exc:
        return {"ok": False, "relative_path": relative_path, "error": _error(exc.code, exc.message)}

    if target.exists():
        if not target.is_file():
            return {"ok": False, "relative_path": relative_path, "error": _error("NOT_A_FILE", "path is not a file")}
        if not os.access(target, os.W_OK):
            return {"ok": False, "relative_path": relative_path, "error": _error("READ_ONLY", "file is read-only")}
        if expected_version is not None:
            current_version = str(target.stat().st_mtime)
            if current_version != expected_version:
                return {
                    "ok": False,
                    "relative_path": relative_path,
                    "error": _error("VERSION_CONFLICT", "file has changed on disk since it was read"),
                    "current_version": current_version,
                }

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    new_version = str(target.stat().st_mtime)
    return {"ok": True, "relative_path": relative_path, "version": new_version}


def artifact_identity(relative_path: str) -> str:
    """Deterministic per-file artifact identity derived from the file's relative path."""
    return hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:16]
