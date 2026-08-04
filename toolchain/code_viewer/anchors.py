"""Physical-line declaration index used for CodeViewer's cross-stage Anchor.

Deliberately independent of the parser: a plain regex + brace-depth scan over
raw source lines, so it keeps working on syntactically invalid source (the
parser would simply raise). This mirrors the approach already used by
frontend/lsp/core.py's `_scan_symbols`, extended to also compute each
declaration's end line (needed to highlight a whole block, not just its
header). See docs/development/code_viewer_design.md §6 and §15 (decision 2)
for why this isn't shared with the LSP scanner yet.
"""

from __future__ import annotations

import re

from .model import Anchor

_HEADER_PATTERN = re.compile(
    r"^\s*(?:(?:pub|export)\s+)?(module|model|calculation|fn|struct|enum)\s+([A-Za-z_]\w*)\b"
)

_KIND_ALIASES = {"module": "module", "model": "module", "fn": "function"}

# How far past a declaration header to look for its opening brace. Function
# signatures may wrap parameters across a few physical lines; this bounds the
# search so a malformed/truncated file can't make the scan run away.
_MAX_HEADER_LOOKAHEAD = 20


def scan_anchors(source: str) -> tuple[Anchor, ...]:
    lines = [_strip_line_comment(raw) for raw in source.splitlines()]
    anchors: list[Anchor] = []
    for index, text in enumerate(lines):
        match = _HEADER_PATTERN.match(text)
        if match is None:
            continue
        kind = _KIND_ALIASES.get(match.group(1), match.group(1))
        symbol = match.group(2)
        open_line = _find_open_brace_line(lines, index)
        if open_line is None:
            continue
        end_line = _find_matching_close_line(lines, open_line)
        if end_line is None:
            continue
        anchors.append(
            Anchor(
                symbol=symbol,
                kind=kind,
                source_line=index + 1,
                source_end_line=end_line + 1,
            )
        )
    return tuple(anchors)


def _find_open_brace_line(lines: list[str], start: int) -> int | None:
    limit = min(start + _MAX_HEADER_LOOKAHEAD, len(lines))
    for index in range(start, limit):
        if "{" in lines[index]:
            return index
    return None


def _find_matching_close_line(lines: list[str], open_line: int) -> int | None:
    depth = 0
    for index in range(open_line, len(lines)):
        depth += lines[index].count("{") - lines[index].count("}")
        if depth <= 0:
            return index
    return None


def _strip_line_comment(raw: str) -> str:
    """Best-effort `//` comment stripper. Does not track braces inside string
    literals — a known limitation shared with the LSP's line-based scanner."""
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(raw):
        char = raw[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in {'"', "'"}:
            quote = char
        elif raw.startswith("//", index):
            return raw[:index]
        index += 1
    return raw
