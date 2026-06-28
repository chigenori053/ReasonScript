from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from frontend.language_surface.integration import compile_program
from frontend.language_surface.parser import parse
from playground.backend.analyzer import analyze_ir
from playground.backend.engine import extract_knowledge, simulate
from playground.backend.language_audit import run_language_audit


ROOT = Path(__file__).resolve().parents[1]
SOURCE = """
module Timestamp {
    fn Value() -> int {
        return 42
    }

    calculation Result {
        result = Value()
    }
}
"""


def test_tst_001_datetime_utcnow_is_not_used():
    matches = []
    for path in ROOT.rglob("*.py"):
        if ".git" in path.parts or "node_modules" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "utc" + "now(" in text:
            matches.append(str(path.relative_to(ROOT)))

    assert matches == []


def test_tst_002_knowledge_uses_timezone_aware_utc_timestamp():
    ir = compile_program(parse(SOURCE))[0]
    simulation = simulate(ir)
    knowledge = extract_knowledge(ir, simulation)

    assert _is_utc_timestamp(knowledge["generated_at"])


def test_tst_002_playground_validation_export_uses_allowed_api():
    source = (ROOT / "playground" / "backend" / "main.py").read_text(encoding="utf-8")

    assert '"generated_at": datetime.now(UTC).isoformat()' in source
    assert '"created_at": datetime.now(UTC).isoformat()' in source


def test_tst_004_playground_analyzer_exports_timezone_aware_timestamp():
    ir = compile_program(parse(SOURCE))[0]
    simulation = simulate(ir)
    analysis = analyze_ir(ir, simulation)

    assert _is_utc_timestamp(analysis["quality"]["generated_at"])


def test_tst_005_language_audit_exports_timezone_aware_timestamp():
    audit = run_language_audit()

    assert _is_utc_timestamp(audit["generated_at"])


def test_tst_005_knowledge_timestamp_format_is_deterministic():
    ir = compile_program(parse(SOURCE))[0]
    simulation = simulate(ir)

    first = extract_knowledge(ir, simulation)
    second = extract_knowledge(ir, simulation)

    assert first["generated_at"] == "1970-01-01T00:00:00+00:00"
    assert first["generated_at"] == second["generated_at"]


def _is_utc_timestamp(value: str) -> bool:
    parsed = datetime.fromisoformat(value)
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)
