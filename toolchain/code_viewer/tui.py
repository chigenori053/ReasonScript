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

from .model import Anchor, Stage, ViewerDocument, ViewerState
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


def run_tui(document: ViewerDocument, *, initial_stage: Stage = Stage.SOURCE) -> int:
    locale.setlocale(locale.LC_ALL, "")
    return curses.wrapper(_main, document, initial_stage)


def _main(stdscr, document: ViewerDocument, initial_stage: Stage) -> int:
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

    state = ViewerState(document=document, active_stage=initial_stage, cursor_line=1)
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

    # `?` and `d` are mutually exclusive overlay toggles; switching to one
    # closes the other rather than stacking them.
    if key == ord("?"):
        return replace(state, show_help=not state.show_help, show_diagnostics=False, status_message=None)
    if key == ord("d"):
        return replace(state, show_diagnostics=not state.show_diagnostics, show_help=False, status_message=None)
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
