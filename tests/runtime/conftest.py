"""Shared helpers for the P0 runtime tests (execution budget, counters,
fast-path equivalence, reasoning event modes). Every test talks to the
native host through the same request bridge `reason run` uses."""

from __future__ import annotations

import pytest

from frontend.computation_ir import lower_program, validate_program
from frontend.computation_ir.optimizer import optimize_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.language_surface import parse

HOST = find_binary()

DECLARATIONS = """
    struct Row {
        value: int
    }
"""


def lower(body: str, *, declarations: str = DECLARATIONS) -> dict:
    ir = optimize_program(lower_program(parse(
        f"module M {{\n{declarations}\n calculation Answer {{\n{body}\n }}\n}}")))
    assert validate_program(ir) == []
    return ir


def execute(body: str, *, mode: str = "off", limits: dict | None = None, **options):
    return run_ir(lower(body), binary=HOST, trace_enabled=mode != "off",
                  trace_config={"mode": mode}, limits=limits or {}, **options)


@pytest.fixture(autouse=True)
def _require_host():
    if HOST is None:
        pytest.skip("native runtime host is not built")
