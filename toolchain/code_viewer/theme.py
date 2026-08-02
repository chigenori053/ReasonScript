"""StyleRole -> abstract terminal attributes. No curses import here.

Curses is confined to tui.py alone (see that module's docstring for why);
this mapping stays a plain, curses-free dataclass lookup so it's testable
without a terminal and reusable by any future rendering backend that wants
the same 8-color palette (design doc §8: "256色やtruecolorは使わない").
"""

from __future__ import annotations

from dataclasses import dataclass

from .render import StyleRole


@dataclass(frozen=True)
class TerminalStyle:
    bold: bool = False
    reverse: bool = False
    color: str | None = None  # one of the 8 standard ANSI color names, or None


_PALETTE: dict[StyleRole, TerminalStyle] = {
    StyleRole.DEFAULT: TerminalStyle(),
    StyleRole.HEADER: TerminalStyle(bold=True),
    StyleRole.STATUS: TerminalStyle(reverse=True),
    StyleRole.DIAGNOSTIC: TerminalStyle(color="red", bold=True),
    StyleRole.CORRELATED: TerminalStyle(color="yellow", bold=True),
    StyleRole.CURSOR: TerminalStyle(reverse=True),
}


def style_for(role: StyleRole, *, color_enabled: bool) -> TerminalStyle:
    """Resolve a StyleRole to concrete attributes. With color disabled
    (NO_COLOR, --no-color, or a terminal that lacks color support), color
    drops out but bold/reverse survive — matches design doc §8's fallback:
    "ハイライトは反転表示のみで表現する"."""
    style = _PALETTE.get(role, TerminalStyle())
    if color_enabled:
        return style
    return TerminalStyle(bold=style.bold, reverse=style.reverse, color=None)
