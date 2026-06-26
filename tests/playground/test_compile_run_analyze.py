from __future__ import annotations

from frontend.language_surface.integration import compile_program
from frontend.language_surface.parser import parse
from playground.backend.analyzer import analyze_ir
from playground.backend.engine import simulate


SOURCE = """
module Playground {
    calculation Value {
        result = 1
    }
}
"""


def test_playground_compile_run_analyze_sequence() -> None:
    reason_ir = compile_program(parse(SOURCE))[0]
    simulation = simulate(reason_ir)
    analysis = analyze_ir(reason_ir, simulation)

    assert reason_ir["schema_version"] == "reason-ir/0.1"
    assert simulation["success"] is True
    assert analysis["runtime_trace"]["success"] is True
    assert analysis["determinism"]["overall_deterministic"] is True
    assert analysis["quality"]["overall_pct"] >= 90
