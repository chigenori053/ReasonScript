from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "frontend" / "compiler_fixtures"
VALID_FIXTURES = FIXTURES / "valid"
INVALID_FIXTURES = FIXTURES / "invalid"
EXPECTED_FIXTURES = FIXTURES / "expected"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_name(path: Path) -> str:
    return path.name.removesuffix(".ast.json")
