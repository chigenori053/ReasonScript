"""Project file tree: scan a directory for .rsn files, then flatten it into
rows respecting an expand/collapse state.

Pure and deterministic — one filesystem read at scan time, no watching, no
mutation. See docs/development/code_viewer_design.md §17. FileTreeNode /
FileTreeRow are owned by this module rather than model.py, mirroring how
render.py owns its own Span/Line/Frame vocabulary: nothing outside
filetree.py + render.py + tui.py needs these types.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# Directories never descended into, regardless of .rsn contents. Matches the
# ignore list scripts/build_update_package.py already uses for packaging, so
# there's one convention for "irrelevant project noise" rather than two.
_IGNORED_DIR_NAMES = frozenset(
    {"__pycache__", ".venv", "node_modules", ".git", "target", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
)


@dataclass(frozen=True)
class FileTreeNode:
    path: Path
    name: str
    is_directory: bool
    children: tuple["FileTreeNode", ...] = ()


@dataclass(frozen=True)
class FileTreeRow:
    path: Path
    name: str
    is_directory: bool
    depth: int
    expanded: bool  # only meaningful when is_directory is True


def scan_project_tree(root: Path) -> FileTreeNode | None:
    """Scan `root` for .rsn files, keeping only .rsn files and the
    directories that (transitively) contain at least one. Returns None if
    `root` has no .rsn files anywhere beneath it (including if `root`
    itself doesn't exist or isn't readable)."""
    return _scan_directory(root.resolve())


def _scan_directory(path: Path) -> FileTreeNode | None:
    try:
        entries = sorted(path.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name.lower()))
    except OSError:
        return None

    children: list[FileTreeNode] = []
    for entry in entries:
        if entry.is_symlink():
            continue  # avoids traversal loops; matches design doc §17.11 point 4
        if entry.is_dir():
            if entry.name in _IGNORED_DIR_NAMES or entry.name.startswith("."):
                continue
            child = _scan_directory(entry)
            if child is not None:
                children.append(child)
        elif entry.is_file() and entry.suffix == ".rsn":
            children.append(FileTreeNode(path=entry, name=entry.name, is_directory=False))

    if not children:
        return None
    return FileTreeNode(path=path, name=path.name, is_directory=True, children=tuple(children))


def first_file(node: FileTreeNode) -> FileTreeNode | None:
    """The most-immediately-relevant file to open by default when a
    directory (not a specific file) is given to `reason view` — files at
    this level before descending into subdirectories, so a shallow, obvious
    entry point wins over an arbitrary deep one."""
    for child in node.children:
        if not child.is_directory:
            return child
    for child in node.children:
        if child.is_directory:
            found = first_file(child)
            if found is not None:
                return found
    return None


def flatten_file_tree(root: FileTreeNode | None, expanded: frozenset[Path]) -> tuple[FileTreeRow, ...]:
    """Flatten the root's *children* into display rows — the root itself
    isn't a row; its path is what the file-tree header line shows instead."""
    if root is None:
        return ()
    rows: list[FileTreeRow] = []
    for child in root.children:
        _flatten_into(rows, child, depth=0, expanded=expanded)
    return tuple(rows)


def _flatten_into(rows: list[FileTreeRow], node: FileTreeNode, *, depth: int, expanded: frozenset[Path]) -> None:
    is_expanded = node.path in expanded
    rows.append(FileTreeRow(path=node.path, name=node.name, is_directory=node.is_directory, depth=depth, expanded=is_expanded))
    if node.is_directory and is_expanded:
        for child in node.children:
            _flatten_into(rows, child, depth=depth + 1, expanded=expanded)


def ancestor_directories(root: FileTreeNode, target: Path) -> frozenset[Path]:
    """Directories on the path from `root` down to `target`, for
    auto-expanding the tree just enough to reveal the file that's
    currently open (design doc §17.11 point 1)."""
    found: set[Path] = set()
    _collect_ancestors(root, target, found)
    return frozenset(found)


def _collect_ancestors(node: FileTreeNode, target: Path, found: set[Path]) -> bool:
    if node.path == target:
        return True
    if not node.is_directory:
        return False
    for child in node.children:
        if _collect_ancestors(child, target, found):
            found.add(node.path)
            return True
    return False
