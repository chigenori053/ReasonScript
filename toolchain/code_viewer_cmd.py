"""reason view — browse a .rsn source file alongside its compiled stages.

Phase 3 (see docs/development/code_viewer_design.md §14): `--json`,
`--plain`, and the interactive curses TUI are all implemented. Non-TTY
output still auto-degrades to `--plain` (design doc §10), and a TTY that
can't import curses — Windows without the `windows-curses` extra — degrades
the same way instead of crashing (design doc §11, diagnostic CV-006).
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from toolchain.code_viewer import (
    ProjectionError,
    Stage,
    ViewerState,
    project,
    render,
    to_json_value,
    to_plain_text,
)


_STAGE_NAMES = {stage.value for stage in Stage}
_VALUE_OPTIONS = ("--stage", "--module", "--width")


def run(args: list[str], project_root: Path) -> int:
    positional = _positional_args(args)
    if not positional:
        print("Usage: reason view <source.rsn> [--stage <name>] [--module <name>] [--json] [--plain] [--width <n>]")
        return 1

    source_path = _resolve_path(project_root, positional[0])
    if not source_path.is_file():
        print(f"Error:\n\nCV-001\n\nSource file not found: {source_path}")
        return 1

    stage_name = _option(args, "--stage")
    if stage_name is not None and stage_name not in _STAGE_NAMES:
        print(f"Error:\n\nCV-002\n\nUnknown stage: {stage_name}\nValid stages: {', '.join(sorted(_STAGE_NAMES))}")
        return 1

    module = _option(args, "--module")
    source = source_path.read_text(encoding="utf-8")

    try:
        document = project(source, source_path, module=module)
    except ProjectionError as error:
        print(f"Error:\n\n{error.code}\n\n{error.message}")
        return 1

    if "--json" in args:
        print(json.dumps(to_json_value(document), indent=2))
        return 0 if document.ok else 2

    if "--plain" in args or not sys.stdout.isatty():
        width = _resolve_width(args)
        stage = Stage(stage_name) if stage_name else Stage.SOURCE
        print(_plain_output(document, stage, width))
        return 0 if document.ok else 2

    stage = Stage(stage_name) if stage_name else Stage.SOURCE
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

    return run_tui(document, initial_stage=stage)


def _plain_output(document, stage, width: int) -> str:
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
