from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "frontend" / "parser_fixtures"
VALID_FIXTURES = FIXTURES / "valid"
INVALID_FIXTURES = FIXTURES / "invalid"


def load_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")
