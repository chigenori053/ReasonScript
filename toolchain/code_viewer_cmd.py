"""reason view — browse a .rsn source file (or a project's file tree)
alongside its compiled stages.

`--json`, `--plain`, and the interactive curses TUI are all implemented
(design doc P1-P5). Non-TTY output auto-degrades to `--plain` (design doc
§10), and a TTY that can't import curses — Windows without the
`windows-curses` extra — degrades the same way instead of crashing (design
doc §11, diagnostic CV-006).

§17 adds a toggleable file-tree overlay (the `e` key) for browsing a
project instead of naming one file up front: pass a directory, or nothing
at all, to start with the tree open.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from toolchain.code_viewer import (
    ProjectionError,
    Stage,
    ViewerDocument,
    ViewerState,
    ancestor_directories,
    first_file,
    project,
    render,
    scan_project_tree,
    to_json_value,
    to_plain_text,
)
from toolchain.code_viewer.filetree import FileTreeNode


_STAGE_NAMES = {stage.value for stage in Stage}
_VALUE_OPTIONS = ("--stage", "--module", "--width", "--root")


def run(args: list[str], project_root: Path) -> int:
    positional = _positional_args(args)
    explicit_output = "--json" in args or "--plain" in args

    stage_name = _option(args, "--stage")
    if stage_name is not None and stage_name not in _STAGE_NAMES:
        print(f"Error:\n\nCV-002\n\nUnknown stage: {stage_name}\nValid stages: {', '.join(sorted(_STAGE_NAMES))}")
        return 1
    stage = Stage(stage_name) if stage_name else Stage.SOURCE
    module = _option(args, "--module")

    target = _resolve_path(project_root, positional[0]) if positional else project_root

    if not positional or target.is_dir():
        if explicit_output:
            print(
                "Error:\n\nCV-007\n\n"
                "--json/--plain requires a specific .rsn file, not a directory.\n"
                "Pass a file, or omit --json/--plain to browse interactively."
            )
            return 1
        if not sys.stdout.isatty():
            print("Usage: reason view <source.rsn> [--stage <name>] [--module <name>] [--json] [--plain] [--width <n>]")
            return 1
        return _run_browse(args, target, stage=stage, module=module)

    if not target.is_file():
        print(f"Error:\n\nCV-001\n\nSource file not found: {target}")
        return 1

    source = target.read_text(encoding="utf-8")
    try:
        document = project(source, target, module=module)
    except ProjectionError as error:
        print(f"Error:\n\n{error.code}\n\n{error.message}")
        return 1

    if "--json" in args:
        print(json.dumps(to_json_value(document), indent=2))
        return 0 if document.ok else 2

    if "--plain" in args or not sys.stdout.isatty():
        width = _resolve_width(args)
        print(_plain_output(document, stage, width))
        return 0 if document.ok else 2

    # Interactive: the tree is scanned and available (closed) even though an
    # explicit file was named, so `e` works immediately without a pause.
    tree_root = _resolve_tree_root(args, project_root, project_root)
    tree = scan_project_tree(tree_root)
    tree_expanded = ancestor_directories(tree, target) if tree is not None else frozenset()
    return _launch_tui(
        args, document, stage=stage, tree_root=tree_root, tree=tree,
        tree_expanded=tree_expanded, show_file_tree=False,
    )


def _run_browse(args: list[str], directory: Path, *, stage: Stage, module: str | None) -> int:
    tree_root = _resolve_tree_root(args, directory, directory)
    tree = scan_project_tree(tree_root)
    entry = first_file(tree) if tree is not None else None
    if entry is None or tree is None:
        print(f"Error:\n\nCV-008\n\nNo .rsn files found under: {tree_root}")
        return 1

    source = entry.path.read_text(encoding="utf-8")
    try:
        document = project(source, entry.path, module=module)
    except ProjectionError as error:
        print(f"Error:\n\n{error.code}\n\n{error.message}")
        return 1

    tree_expanded = ancestor_directories(tree, entry.path)
    return _launch_tui(
        args, document, stage=stage, tree_root=tree_root, tree=tree,
        tree_expanded=tree_expanded, show_file_tree=True,
    )


def _launch_tui(
    args: list[str],
    document: ViewerDocument,
    *,
    stage: Stage,
    tree_root: Path,
    tree: FileTreeNode | None,
    tree_expanded: frozenset[Path],
    show_file_tree: bool,
) -> int:
    try:
        from toolchain.code_viewer.tui import run_tui
    except ImportError:
        print(
            "note: interactive viewer requires windows-curses on this platform.\n"
            "      install with: pip install 'reasonscript[viewer]'\n"
            "      falling back to --plain output.",
            file=sys.stderr,
        )
        print(_plain_output(document, stage, _resolve_width(args)))
        return 0 if document.ok else 2

    return run_tui(
        document, initial_stage=stage, tree_root=tree_root, tree=tree,
        tree_expanded=tree_expanded, show_file_tree=show_file_tree,
    )


def _plain_output(document: ViewerDocument, stage: Stage, width: int) -> str:
    active_view = document.stages[stage]
    content_needed = max(len(document.source_lines), len(active_view.nodes), 1)
    height = content_needed + 2  # header row + footer row, no scrolling needed
    state = ViewerState(document=document, active_stage=stage, cursor_line=1)
    return to_plain_text(render(state, width=width, height=height))


def _resolve_width(args: list[str]) -> int:
    value = _option(args, "--width")
    if value is not None:
        try:
            return int(value)
        except ValueError:
            pass
    return shutil.get_terminal_size(fallback=(80, 24)).columns


def _resolve_tree_root(args: list[str], project_root: Path, fallback: Path) -> Path:
    root_option = _option(args, "--root")
    if root_option is not None:
        return _resolve_path(project_root, root_option)
    return fallback


def _resolve_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def _positional_args(args: list[str]) -> list[str]:
    positional: list[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in _VALUE_OPTIONS:
            skip_next = True
            continue
        if arg.startswith("--"):
            continue
        positional.append(arg)
    return positional


def _option(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None
