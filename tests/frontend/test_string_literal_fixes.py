"""Unbalanced delimiters inside string literals (L-005) and escape decoding (L-012)."""

from __future__ import annotations

import pytest

from frontend.language_surface.expressions import _decode_string
from frontend.language_surface.parser import parse


@pytest.mark.parametrize("literal", ['"{"', '"["', '"("', '"}"', '"]"', '")"'])
def test_unbalanced_delimiter_in_string_literal_parses(literal: str) -> None:
    source = (
        "module M {\n  calculation A {\n"
        f"    let x = runtime.print({literal})\n"
        "    result = x\n  }\n}\n"
    )
    parse(source)


def test_string_escapes_decode() -> None:
    assert _decode_string(r'"a\nb\tc"') == "a\nb\tc"
    assert _decode_string(r'"\"q\" \\n"') == '"q" \\n'
    assert _decode_string(r'"C:\data"') == r"C:\data"
