"""ReasonScript CodeViewer — browse .rsn source alongside its compiled stages.

Phase 1 (see docs/development/code_viewer_design.md §14): `project()` only.
Rendering (render.py) and the interactive TUI (tui.py) land in later phases.
"""

from __future__ import annotations

from .model import (
    SCHEMA,
    Anchor,
    Stage,
    StageNode,
    StageView,
    TokenSpan,
    ViewerDocument,
    ViewerState,
)
from .projection import ProjectionError, project
from .render import Frame, Line, Span, StyleRole, render, to_plain_text
from .serialize import to_json_value

__all__ = [
    "SCHEMA",
    "Anchor",
    "Frame",
    "Line",
    "ProjectionError",
    "Span",
    "Stage",
    "StageNode",
    "StageView",
    "StyleRole",
    "TokenSpan",
    "ViewerDocument",
    "ViewerState",
    "project",
    "render",
    "to_json_value",
    "to_plain_text",
]
