"""ViewerState -> Frame. A pure function: no curses, no I/O, no terminal calls.

`render()` is the one interface tui.py (P3) and the `--plain` CLI path share
(design doc §4/§14): a two-pane layout (source with line numbers on the
left, the active compiled stage as a tree on the right), correlated via the
`▸` marker on whichever declaration currently contains the cursor and
whichever stage nodes share its Anchor symbol.

Row-level-only styling (StyleRole distinguishes header/status/cursor/
correlated/diagnostic rows as a whole). Per-token syntax coloring stays
deferred — see docs/development/code_viewer_design.md §8; adding it would
require precise column bookkeeping between the line-number gutter and token
offsets for no visible benefit until it's actually needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .model import Anchor, Stage, StageView, ViewerDocument, ViewerState


MIN_WIDTH = 40
MIN_HEIGHT = 10

_HEADER_ROWS = 1
_FOOTER_ROWS = 1

_STAGE_ORDER = (Stage.SOURCE, Stage.SURFACE, Stage.SEMANTIC, Stage.IR, Stage.PLAN)
_STAGE_LABELS = {
    Stage.SOURCE: "Source",
    Stage.SURFACE: "Surface",
    Stage.SEMANTIC: "Semantic",
    Stage.IR: "IR",
    Stage.PLAN: "Plan",
}


class StyleRole(str, Enum):
    DEFAULT = "default"
    HEADER = "header"
    STATUS = "status"
    DIAGNOSTIC = "diagnostic"
    CORRELATED = "correlated"
    CURSOR = "cursor"


@dataclass(frozen=True)
class Span:
    text: str
    style: StyleRole = StyleRole.DEFAULT


Line = tuple[Span, ...]
Frame = tuple[Line, ...]


def render(state: ViewerState, width: int, height: int) -> Frame:
    """Render one full screen. Callers that want the whole document with no
    scrolling (the `--plain` CLI path) simply pass a `height` large enough
    that nothing gets cropped — see `code_viewer_cmd.py`."""
    width = max(width, MIN_WIDTH)
    height = max(height, MIN_HEIGHT)

    if state.show_help:
        return _render_help(width, height)
    if state.show_diagnostics:
        return _render_diagnostics(state.document, width, height)

    content_height = height - _HEADER_ROWS - _FOOTER_ROWS

    document = state.document
    active_view = document.stages[state.active_stage]
    correlated = _anchor_at_line(document.anchors, state.cursor_line)

    left_width = width // 2 - 1
    right_width = width - left_width - 3  # " | " divider

    lines: list[Line] = [_header_row(document, state, left_width, right_width)]
    lines.extend(
        _content_rows(
            document,
            active_view,
            state,
            correlated,
            content_height,
            left_width,
            right_width,
        )
    )
    lines.append(_footer_row(document, state, width))
    return tuple(lines)


def to_plain_text(frame: Frame) -> str:
    return "\n".join("".join(span.text for span in line) for line in frame)


_HELP_LINES = (
    "CodeViewer — keybindings",
    "",
    "  1-5, Tab / Shift-Tab   switch stage (Source/Surface/Semantic/IR/Plan)",
    "  j/k, Down/Up           move cursor (source pane) or scroll (stage pane)",
    "  Ctrl-d / Ctrl-u        half-page scroll",
    "  n / p                  jump to next / previous declaration",
    "         (or next / previous search match, once a search is active)",
    "  /                      search source text, Enter to confirm, Esc to cancel",
    "  Enter                  focus the stage pane",
    "  Esc                    clear an active search, else return focus to source",
    "  y                      copy the selected stage node's JSON pointer",
    "  d                      toggle the all-stages diagnostics summary",
    "  ?                      toggle this help",
    "  q, Ctrl-c              quit",
    "",
    "Press any key to close this help.",
)


def _render_help(width: int, height: int) -> Frame:
    rows: list[Line] = [
        (Span(_fit(text, width), StyleRole.HEADER if index == 0 else StyleRole.DEFAULT),)
        for index, text in enumerate(_HELP_LINES)
    ]
    while len(rows) < height:
        rows.append((Span(_fit("", width)),))
    return tuple(rows[:height])


def _render_diagnostics(document: ViewerDocument, width: int, height: int) -> Frame:
    """A single place to see every stage's compile problems at once — without
    this, a user would have to flip through each stage individually to
    discover what's broken (design doc §7, the `d` keybinding)."""
    rows: list[Line] = [(Span(_fit("Diagnostics", width), StyleRole.HEADER),), (Span(_fit("", width)),)]
    any_diagnostic = False
    for stage in _STAGE_ORDER:
        view = document.stages[stage]
        if view.available:
            continue
        any_diagnostic = True
        rows.append((Span(_fit(f"[{_STAGE_LABELS[stage]}]", width), StyleRole.HEADER),))
        for diagnostic in view.diagnostics:
            position = diagnostic.location.range.start
            text = f"  {diagnostic.code} at {position.line + 1}:{position.character + 1} — {diagnostic.message}"
            rows.append((Span(_fit(text, width), StyleRole.DIAGNOSTIC),))
        rows.append((Span(_fit("", width)),))
    if not any_diagnostic:
        rows.append((Span(_fit("No diagnostics — every stage compiled cleanly.", width)),))
    rows.append((Span(_fit("Press any key to close.", width)),))
    while len(rows) < height:
        rows.append((Span(_fit("", width)),))
    return tuple(rows[:height])


def _header_row(document: ViewerDocument, state: ViewerState, left_width: int, right_width: int) -> Line:
    left = _fit(document.source_path, left_width)
    stage_label = _STAGE_LABELS[state.active_stage]
    module = document.active_module or "-"
    right = _fit(f"[{stage_label}] module: {module}", right_width)
    return (Span(f"{left} | {right}", StyleRole.HEADER),)


def _footer_row(document: ViewerDocument, state: ViewerState, width: int) -> Line:
    if state.search_input is not None:
        # A vim-style command line while typing — nothing else competes for
        # this row's attention until the search is committed or cancelled.
        return (Span(_fit(f"/{state.search_input}", width), StyleRole.STATUS),)

    tabs = " ".join(
        f"{index + 1}:{_STAGE_LABELS[stage]}{'*' if stage is state.active_stage else ''}"
        for index, stage in enumerate(_STAGE_ORDER)
    )
    # Ordered by priority, most important first, so truncation on a narrow
    # terminal drops the least useful part of the status line rather than
    # eating the quit hint or hiding that some stage failed to compile.
    parts = [tabs, "?:help q:quit"]
    if state.status_message:
        parts.append(state.status_message)
    if state.search_query:
        parts.append(f"search {state.search_query!r} (n/p)")
    if not document.ok:
        failed = sum(1 for view in document.stages.values() if not view.available)
        parts.append(f"{failed} stage error(s), see --stage")
    parts.append(f"line {state.cursor_line}")
    parts.append(f"{len(document.anchors)} declaration(s)")
    status = " | ".join(parts)
    return (Span(_fit(status, width), StyleRole.STATUS),)


def _content_rows(
    document: ViewerDocument,
    active_view: StageView,
    state: ViewerState,
    correlated: Anchor | None,
    content_height: int,
    left_width: int,
    right_width: int,
) -> list[Line]:
    declared_lines = {anchor.source_line: anchor.symbol for anchor in document.anchors}
    correlated_symbol = correlated.symbol if correlated is not None else None

    source_slice = document.source_lines[state.source_scroll : state.source_scroll + content_height]
    right_rows = _right_pane_rows(active_view, state, correlated_symbol, content_height)

    total_lines = len(document.source_lines)
    num_width = max(len(str(total_lines)), 1)

    rows: list[Line] = []
    for offset in range(content_height):
        line_no = state.source_scroll + offset + 1
        left_marked = bool(correlated_symbol) and declared_lines.get(line_no) == correlated_symbol
        if offset < len(source_slice):
            marker = "▸" if left_marked else " "
            left_text = f"{marker}{line_no:>{num_width}} {source_slice[offset]}"
        else:
            left_text = ""
        right_text, right_marked, right_selected = right_rows[offset] if offset < len(right_rows) else ("", False, False)
        has_right_content = offset < len(right_rows)

        # Left and right panes scroll independently, so a row's two halves
        # can land next to each other purely by coincidence of vertical
        # offset — style each half from its OWN correlation state, never
        # from the other half's, or an unrelated line lights up whenever an
        # unrelated stage row happens to share its row index (see the P3
        # implementation notes: caught by manual testing, not by a golden
        # text diff, since to_plain_text() can't see per-span style).
        if state.focus == "source" and line_no == state.cursor_line:
            left_style = StyleRole.CURSOR
        elif left_marked:
            left_style = StyleRole.CORRELATED
        else:
            left_style = StyleRole.DEFAULT

        if not active_view.available and has_right_content:
            right_style = StyleRole.DIAGNOSTIC
        elif right_selected:
            right_style = StyleRole.CURSOR
        elif right_marked:
            right_style = StyleRole.CORRELATED
        else:
            right_style = StyleRole.DEFAULT

        rows.append(
            (
                Span(_fit(left_text, left_width), left_style),
                Span(" | "),
                Span(_fit(right_text, right_width), right_style),
            )
        )
    return rows


def _right_pane_rows(
    active_view: StageView, state: ViewerState, correlated_symbol: str | None, content_height: int
) -> list[tuple[str, bool, bool]]:
    if not active_view.available:
        messages = [f"[{d.code}] {d.message}" for d in active_view.diagnostics] or ["(stage unavailable)"]
        return [(message, False, False) for message in messages]
    visible = active_view.nodes[state.stage_scroll : state.stage_scroll + content_height]
    rows: list[tuple[str, bool, bool]] = []
    for local_index, node in enumerate(visible):
        absolute_index = state.stage_scroll + local_index
        marked = bool(correlated_symbol) and node.anchor == correlated_symbol
        selected = state.focus == "stage" and absolute_index == state.stage_cursor
        marker = "▸" if marked else " "
        rows.append((f"{marker}{'  ' * node.depth}{node.label}", marked, selected))
    return rows


def _anchor_at_line(anchors: tuple[Anchor, ...], line: int) -> Anchor | None:
    candidates = [a for a in anchors if a.source_line <= line <= a.source_end_line]
    if not candidates:
        return None
    return max(candidates, key=lambda a: a.source_line)


def _fit(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) > width:
        return text[: max(width - 1, 0)] + "…"
    return text.ljust(width)
