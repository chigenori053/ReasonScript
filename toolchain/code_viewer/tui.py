"""Interactive curses front-end for `reason view`.

The only file in CodeViewer allowed to `import curses` (design doc §4). A
failure to import curses here — Windows without the `windows-curses` extra
— propagates as ImportError to code_viewer_cmd.py, which catches it and
falls back to `--plain` output instead of crashing (design doc §11/§15,
decision 1 and diagnostic CV-006).

All state mutation happens here, in response to keypresses; render.py stays
a pure function of ViewerState and knows nothing about curses or input.
"""

from __future__ import annotations

import curses
import locale
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

from .filetree import FileTreeNode, ancestor_directories, flatten_file_tree
from .model import Anchor, Stage, ViewerDocument, ViewerState
from .projection import project
from .render import MIN_HEIGHT, MIN_WIDTH, render
from .theme import style_for


_STAGE_ORDER = (Stage.SOURCE, Stage.SURFACE, Stage.SEMANTIC, Stage.IR, Stage.PLAN)
_HEADER_ROWS = 1
_FOOTER_ROWS = 1

_QUIT_KEYS = {ord("q"), 3}  # 3 == Ctrl-C delivered as a keypress, not SIGINT
_CTRL_D = 4
_CTRL_U = 21
_ESC = 27
_BACKSPACE_KEYS = {curses.KEY_BACKSPACE, 127, 8}

# Shelled out to, in order, rather than adding a clipboard pip dependency —
# consistent with the project's zero-required-dependency stance (design doc
# §11). None found or all failing just means `y` reports it couldn't copy.
_CLIPBOARD_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("pbcopy",),
    ("wl-copy",),
    ("xclip", "-selection", "clipboard"),
    ("xsel", "--clipboard", "--input"),
    ("clip",),  # Windows, when reached via a terminal that does have curses
)


def run_tui(
    document: ViewerDocument,
    *,
    initial_stage: Stage = Stage.SOURCE,
    tree_root: Path | None = None,
    tree: FileTreeNode | None = None,
    tree_expanded: frozenset[Path] = frozenset(),
    show_file_tree: bool = False,
) -> int:
    """tree_root/tree/tree_expanded/show_file_tree are set by
    code_viewer_cmd.py (design doc §17): tree_root/tree are scanned once
    before the TUI starts (scanning is I/O — it doesn't belong in the pure
    render()/​_handle_key() path), and show_file_tree controls whether the
    file picker is the first thing the user sees (when `reason view` was
    given a directory, or no path at all) or starts closed (an explicit
    .rsn file was given, matching every pre-§17 invocation unchanged)."""
    locale.setlocale(locale.LC_ALL, "")
    tree_cursor = 0
    if show_file_tree:
        # Starting straight into the tree (a directory or omitted path was
        # given) — land the cursor on the auto-picked document, matching
        # what pressing `e` later would do (_reveal_path / _toggle_file_tree).
        tree_expanded, tree_cursor = _reveal_path(tree, tree_expanded, Path(document.source_path).resolve())
    initial_state = ViewerState(
        document=document,
        active_stage=initial_stage,
        cursor_line=1,
        tree_root=tree_root,
        tree=tree,
        tree_expanded=tree_expanded,
        tree_cursor=tree_cursor,
        show_file_tree=show_file_tree,
    )
    return curses.wrapper(_main, initial_state)


def _main(stdscr, initial_state: ViewerState) -> int:
    curses.curs_set(0)
    stdscr.keypad(True)
    color_enabled = curses.has_colors()
    pairs: dict[str, int] = {}
    if color_enabled:
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        pairs = _init_pairs()

    state = initial_state
    while True:
        height, width = stdscr.getmaxyx()

        # render() clamps internally to MIN_WIDTH x MIN_HEIGHT so it never
        # crashes, but blitting that clamped frame onto a REAL terminal
        # smaller than that just shows a confusing partial slice. Say so
        # plainly instead (design doc §15 decision 1 / diagnostic CV-004).
        # curses.KEY_RESIZE naturally falls through to the next loop
        # iteration here, which re-measures — no special-casing needed.
        if height < MIN_HEIGHT or width < MIN_WIDTH:
            _blit_too_small(stdscr, width, height)
            key = stdscr.getch()
            if key in _QUIT_KEYS:
                return 0
            continue

        frame = render(state, width=width, height=height)
        _blit(stdscr, frame, color_enabled=color_enabled, pairs=pairs)
        key = stdscr.getch()
        if key in _QUIT_KEYS:
            return 0
        content_height = max(height, MIN_HEIGHT) - _HEADER_ROWS - _FOOTER_ROWS
        state = _handle_key(state, key, content_height)
        state = _apply_pending_open(state)


def _blit_too_small(stdscr, width: int, height: int) -> None:
    stdscr.erase()
    message = f"Terminal too small ({width}x{height}); need at least {MIN_WIDTH}x{MIN_HEIGHT}. q to quit."
    try:
        stdscr.addstr(0, 0, message[: max(width, 0)])
    except curses.error:
        pass
    stdscr.refresh()


def _blit(stdscr, frame, *, color_enabled: bool, pairs: dict[str, int]) -> None:
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    for row, line in enumerate(frame):
        if row >= max_y:
            break
        col = 0
        for span in line:
            if col >= max_x:
                break
            style = style_for(span.style, color_enabled=color_enabled)
            attr = curses.A_BOLD if style.bold else 0
            attr |= curses.A_REVERSE if style.reverse else 0
            if style.color and style.color in pairs:
                attr |= curses.color_pair(pairs[style.color])
            text = span.text[: max_x - col]
            try:
                # Writing the screen's very last cell raises curses.error on
                # some terminals — a well-known quirk, not a real failure.
                stdscr.addstr(row, col, text, attr)
            except curses.error:
                pass
            col += len(text)
    stdscr.refresh()


def _init_pairs() -> dict[str, int]:
    palette = {
        "red": curses.COLOR_RED,
        "yellow": curses.COLOR_YELLOW,
        "green": curses.COLOR_GREEN,
        "cyan": curses.COLOR_CYAN,
        "magenta": curses.COLOR_MAGENTA,
        "blue": curses.COLOR_BLUE,
    }
    pairs: dict[str, int] = {}
    for index, (name, color) in enumerate(palette.items(), start=1):
        try:
            curses.init_pair(index, color, -1)
        except curses.error:
            continue
        pairs[name] = index
    return pairs


def _handle_key(state: ViewerState, key: int, content_height: int) -> ViewerState:
    if state.search_input is not None:
        return _handle_search_typing(state, key, content_height)

    # `?`, `d`, `e` are mutually exclusive overlay toggles; switching to one
    # closes whichever other one was open rather than stacking them.
    if key == ord("?"):
        return replace(state, show_help=not state.show_help, show_diagnostics=False, show_file_tree=False, status_message=None)
    if key == ord("d"):
        return replace(state, show_diagnostics=not state.show_diagnostics, show_help=False, show_file_tree=False, status_message=None)
    if key == ord("e"):
        return _toggle_file_tree(state)

    if state.show_file_tree:
        return _handle_file_tree_key(state, key, content_height)
    if state.show_help or state.show_diagnostics:
        return replace(state, show_help=False, show_diagnostics=False)  # any other key closes it

    state = replace(state, status_message=None)  # transient — clear unless a branch below sets a new one

    if key == ord("/"):
        return replace(state, search_input="")

    if key == _ESC:
        if state.search_query is not None:
            return replace(state, search_query=None)
        return replace(state, focus="source")

    if key == ord("\t"):
        return _cycle_stage(state, 1)
    if hasattr(curses, "KEY_BTAB") and key == curses.KEY_BTAB:
        return _cycle_stage(state, -1)
    if ord("1") <= key <= ord("5"):
        return replace(state, active_stage=_STAGE_ORDER[key - ord("1")], stage_scroll=0, stage_cursor=0)

    if key in (ord("j"), curses.KEY_DOWN):
        return _move(state, 1, content_height)
    if key in (ord("k"), curses.KEY_UP):
        return _move(state, -1, content_height)
    if key == _CTRL_D:
        return _move(state, max(content_height // 2, 1), content_height)
    if key == _CTRL_U:
        return _move(state, -max(content_height // 2, 1), content_height)

    if key == ord("n"):
        return _search_step(state, 1, content_height) if state.search_query else _jump_anchor(state, 1, content_height)
    if key == ord("p"):
        return _search_step(state, -1, content_height) if state.search_query else _jump_anchor(state, -1, content_height)

    if key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
        return replace(state, focus="stage")

    if key == ord("y"):
        return _copy_node(state)

    return state


def _cycle_stage(state: ViewerState, direction: int) -> ViewerState:
    index = _STAGE_ORDER.index(state.active_stage)
    next_index = (index + direction) % len(_STAGE_ORDER)
    return replace(state, active_stage=_STAGE_ORDER[next_index], stage_scroll=0, stage_cursor=0)


def _move(state: ViewerState, delta: int, content_height: int) -> ViewerState:
    if state.focus == "stage":
        nodes = state.document.stages[state.active_stage].nodes
        if not nodes:
            return state
        cursor = min(max(state.stage_cursor + delta, 0), len(nodes) - 1)
        scroll = _follow_cursor(state.stage_scroll, cursor + 1, content_height)
        return replace(state, stage_cursor=cursor, stage_scroll=scroll)

    total_lines = len(state.document.source_lines)
    cursor = min(max(state.cursor_line + delta, 1), max(total_lines, 1))
    scroll = _follow_cursor(state.source_scroll, cursor, content_height)
    return replace(state, cursor_line=cursor, source_scroll=scroll)


def _follow_cursor(scroll: int, cursor_line: int, content_height: int) -> int:
    if content_height <= 0:
        return scroll
    if cursor_line - 1 < scroll:
        return cursor_line - 1
    if cursor_line - 1 >= scroll + content_height:
        return cursor_line - content_height
    return scroll


def _jump_anchor(state: ViewerState, direction: int, content_height: int) -> ViewerState:
    anchors: tuple[Anchor, ...] = tuple(sorted(state.document.anchors, key=lambda a: a.source_line))
    if not anchors:
        return state
    if direction > 0:
        candidates = [a for a in anchors if a.source_line > state.cursor_line]
        target = candidates[0] if candidates else anchors[0]
    else:
        candidates = [a for a in anchors if a.source_line < state.cursor_line]
        target = candidates[-1] if candidates else anchors[-1]
    scroll = _follow_cursor(state.source_scroll, target.source_line, content_height)
    return replace(state, cursor_line=target.source_line, source_scroll=scroll, focus="source")


def _handle_search_typing(state: ViewerState, key: int, content_height: int) -> ViewerState:
    buffer = state.search_input or ""
    if key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
        if not buffer:
            return replace(state, search_input=None, search_query=None)
        return _commit_search(replace(state, search_input=None, search_query=buffer), content_height)
    if key == _ESC:
        return replace(state, search_input=None)
    if key in _BACKSPACE_KEYS:
        return replace(state, search_input=buffer[:-1])
    if 32 <= key < 127:  # printable ASCII
        return replace(state, search_input=buffer + chr(key))
    return state  # ignore other control/function keys while typing


def _search_matches(document: ViewerDocument, query: str) -> list[int]:
    needle = query.lower()
    return [index + 1 for index, line in enumerate(document.source_lines) if needle in line.lower()]


def _commit_search(state: ViewerState, content_height: int) -> ViewerState:
    query = state.search_query or ""
    matches = _search_matches(state.document, query)
    if not matches:
        # Leaving search_query set here would silently disable n/p forever
        # (no matches means _search_step is a permanent no-op) — clear it so
        # n/p fall back to anchor-jump instead of going quiet.
        return replace(state, search_query=None, status_message=f"no matches for {query!r}")
    candidates = [line for line in matches if line >= state.cursor_line]
    target = candidates[0] if candidates else matches[0]
    scroll = _follow_cursor(state.source_scroll, target, content_height)
    return replace(
        state,
        cursor_line=target,
        source_scroll=scroll,
        focus="source",
        status_message=f"{len(matches)} match(es) for {query!r}",
    )


def _search_step(state: ViewerState, direction: int, content_height: int) -> ViewerState:
    matches = _search_matches(state.document, state.search_query or "")
    if not matches:
        return state
    if direction > 0:
        candidates = [line for line in matches if line > state.cursor_line]
        target = candidates[0] if candidates else matches[0]
    else:
        candidates = [line for line in matches if line < state.cursor_line]
        target = candidates[-1] if candidates else matches[-1]
    scroll = _follow_cursor(state.source_scroll, target, content_height)
    return replace(state, cursor_line=target, source_scroll=scroll, focus="source")


def _copy_node(state: ViewerState) -> ViewerState:
    if state.focus != "stage":
        return replace(state, status_message="y: focus the stage pane first (Enter)")
    nodes = state.document.stages[state.active_stage].nodes
    if not nodes or state.stage_cursor >= len(nodes):
        return replace(state, status_message="y: nothing selected")
    pointer = nodes[state.stage_cursor].json_pointer
    if _copy_to_clipboard(pointer):
        return replace(state, status_message=f"copied {pointer}")
    return replace(state, status_message=f"could not copy (no clipboard tool found): {pointer}")


def _copy_to_clipboard(text: str) -> bool:
    for command in _CLIPBOARD_COMMANDS:
        if shutil.which(command[0]) is None:
            continue
        try:
            subprocess.run(command, input=text.encode("utf-8"), check=True, timeout=2)
            return True
        except (subprocess.SubprocessError, OSError):
            continue
    return False


# --- file tree (design doc §17) --------------------------------------------


def _reveal_path(tree: FileTreeNode | None, expanded: frozenset[Path], target: Path) -> tuple[frozenset[Path], int]:
    """Expand just enough of `tree` to make `target` visible, and return the
    row index it lands on. Shared by _toggle_file_tree (re-opening the tree
    later) and run_tui's initial state (opening straight into the tree, for
    a directory/omitted-path launch) so both start from the same row,
    instead of leaving the cursor on row 0 while a *different* row is
    highlighted as "currently open" (caught by manual pty testing — see
    docs/development/code_viewer_design.md §17)."""
    if tree is None:
        return expanded, 0
    revealed = expanded | ancestor_directories(tree, target)
    rows = flatten_file_tree(tree, revealed)
    match = next((index for index, row in enumerate(rows) if row.path == target), None)
    return revealed, (match if match is not None else 0)


def _toggle_file_tree(state: ViewerState) -> ViewerState:
    if state.tree_root is None:
        return replace(state, status_message="file tree unavailable (no project root)")
    if state.show_file_tree:
        return replace(state, show_file_tree=False, status_message=None)

    # Every time the tree opens, reveal (and select) wherever the current
    # document lives — not just once at startup — so re-opening the tree
    # after browsing elsewhere always orients the user again.
    current_path = Path(state.document.source_path).resolve()
    expanded, cursor = _reveal_path(state.tree, state.tree_expanded, current_path)
    return replace(
        state, show_help=False, show_diagnostics=False, show_file_tree=True,
        tree_expanded=expanded, tree_cursor=cursor, status_message=None,
    )


def _handle_file_tree_key(state: ViewerState, key: int, content_height: int) -> ViewerState:
    rows = flatten_file_tree(state.tree, state.tree_expanded)
    if not rows:
        return replace(state, show_file_tree=False) if key == _ESC else state

    if key in (ord("j"), curses.KEY_DOWN):
        return _move_tree_cursor(state, rows, 1, content_height)
    if key in (ord("k"), curses.KEY_UP):
        return _move_tree_cursor(state, rows, -1, content_height)
    if key == _CTRL_D:
        return _move_tree_cursor(state, rows, max(content_height // 2, 1), content_height)
    if key == _CTRL_U:
        return _move_tree_cursor(state, rows, -max(content_height // 2, 1), content_height)
    if key in (ord("l"), curses.KEY_RIGHT, curses.KEY_ENTER, ord("\n"), ord("\r")):
        return _activate_tree_row(state, rows)
    if key in (ord("h"), curses.KEY_LEFT):
        return _collapse_tree_row(state, rows)
    if key == _ESC:
        return replace(state, show_file_tree=False)
    return state


def _move_tree_cursor(state: ViewerState, rows, delta: int, content_height: int) -> ViewerState:
    cursor = min(max(state.tree_cursor + delta, 0), len(rows) - 1)
    scroll = _follow_cursor(state.tree_scroll, cursor + 1, content_height)
    return replace(state, tree_cursor=cursor, tree_scroll=scroll)


def _activate_tree_row(state: ViewerState, rows) -> ViewerState:
    row = rows[state.tree_cursor]
    if row.is_directory:
        expanded = (state.tree_expanded - {row.path}) if row.expanded else (state.tree_expanded | {row.path})
        return replace(state, tree_expanded=expanded)
    # Actual file I/O happens in _apply_pending_open, not here — keeps this
    # function (and _handle_key as a whole) a pure state -> state mapping,
    # which is what makes it unit-testable without a real filesystem/curses.
    return replace(state, pending_open=row.path, show_file_tree=False)


def _collapse_tree_row(state: ViewerState, rows) -> ViewerState:
    row = rows[state.tree_cursor]
    if row.is_directory and row.expanded:
        return replace(state, tree_expanded=state.tree_expanded - {row.path})
    if row.depth == 0:
        return state
    for index in range(state.tree_cursor - 1, -1, -1):  # nearest preceding shallower row = parent
        if rows[index].depth == row.depth - 1:
            return replace(state, tree_cursor=index)
    return state


def _apply_pending_open(state: ViewerState) -> ViewerState:
    """Performs the I/O that _handle_key deliberately never does: reading
    the newly-selected file and recompiling it. Called once per loop
    iteration in _main, right after _handle_key."""
    if state.pending_open is None:
        return state
    path = state.pending_open
    try:
        source = path.read_text(encoding="utf-8")
        document = project(source, path)
    except OSError as error:
        return replace(state, pending_open=None, status_message=f"could not open {path.name}: {error}")
    # active_stage carries over (the user's view mode is more likely to
    # stay relevant than any cursor/scroll position from the old file).
    return replace(
        state, document=document, pending_open=None,
        cursor_line=1, source_scroll=0, stage_scroll=0, stage_cursor=0,
        focus="source", status_message=None,
    )
