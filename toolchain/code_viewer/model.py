"""ReasonScript CodeViewer Phase 1 data model.

Pure dataclasses only — no I/O, no curses. See
docs/development/code_viewer_design.md §5 for the design rationale.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from frontend.lsp.model import Diagnostic

from .filetree import FileTreeNode

SCHEMA = "reasonscript-code-viewer/0.1"


class Stage(str, Enum):
    SOURCE = "source"
    SURFACE = "surface"
    SEMANTIC = "semantic"
    IR = "ir"
    PLAN = "plan"


@dataclass(frozen=True)
class Anchor:
    """Cross-stage correlation unit: a top-level declaration, by name and line.

    Not a general source span — see §6 of the design doc for why expression-
    level correlation isn't attempted in v1 (Surface AST has no positions).
    """

    symbol: str
    kind: str  # "module" | "calculation" | "function" | "struct" | "enum"
    source_line: int  # 1-origin
    source_end_line: int  # 1-origin, inclusive


@dataclass(frozen=True)
class TokenSpan:
    """A lexical token, for source syntax highlighting."""

    line: int  # 1-origin
    column: int  # 1-origin
    text: str
    token_type: str


@dataclass(frozen=True)
class StageNode:
    """One row of a stage's tree view."""

    node_id: str  # unique within the stage (its JSON pointer)
    depth: int
    label: str
    anchor: str | None
    json_pointer: str


@dataclass(frozen=True)
class StageView:
    stage: Stage
    nodes: tuple[StageNode, ...]
    available: bool
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True)
class ViewerDocument:
    """Output of projection.project(). Also the --json payload."""

    schema: str
    source_path: str
    source_lines: tuple[str, ...]
    tokens: tuple[TokenSpan, ...]
    anchors: tuple[Anchor, ...]
    stages: Mapping[Stage, StageView]
    module_names: tuple[str, ...]
    active_module: str | None
    ok: bool


@dataclass(frozen=True)
class ViewerState:
    """Input to render(). Everything that changes in response to a keypress."""

    document: ViewerDocument
    active_stage: Stage = Stage.SOURCE
    cursor_line: int = 1
    source_scroll: int = 0
    stage_scroll: int = 0
    stage_cursor: int = 0  # selected index into the active stage's nodes, for `y` to copy
    focus: str = "source"  # "source" | "stage" — which pane j/k/Ctrl-d/Ctrl-u act on
    search_query: str | None = None  # confirmed, active search term; None = no active search
    search_input: str | None = None  # in-progress `/` search buffer; None = not typing
    status_message: str | None = None  # transient footer message (e.g. from `y`), cleared on next key
    show_help: bool = False
    show_diagnostics: bool = False

    # File tree overlay (design doc §17). tree_root is fixed at startup;
    # everything else changes as the tree is browsed.
    show_file_tree: bool = False
    tree_root: Path | None = None
    tree: FileTreeNode | None = None  # scanned once at startup; flatten_file_tree() reads it per-render
    tree_expanded: frozenset[Path] = field(default_factory=frozenset)
    tree_cursor: int = 0
    tree_scroll: int = 0
    pending_open: Path | None = None  # set by _handle_key, consumed by _apply_pending_open in tui.py
