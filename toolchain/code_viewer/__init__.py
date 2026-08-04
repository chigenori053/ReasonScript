"""ReasonScript CodeViewer — browse .rsn source alongside its compiled stages.

`reason view` (see docs/development/code_viewer_design.md). tui.py is
deliberately not imported here — it's the only module allowed to `import
curses`, and code_viewer_cmd.py needs importing it to be able to fail with
a catchable ImportError on platforms without curses (design doc §11).
"""

from __future__ import annotations

from .filetree import (
    FileTreeNode,
    FileTreeRow,
    ancestor_directories,
    first_file,
    flatten_file_tree,
    scan_project_tree,
)
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
    "FileTreeNode",
    "FileTreeRow",
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
    "ancestor_directories",
    "first_file",
    "flatten_file_tree",
    "project",
    "render",
    "scan_project_tree",
    "to_json_value",
    "to_plain_text",
]
