from __future__ import annotations

import json
from pathlib import Path

from conformance.schema_validator import SchemaValidator
from frontend.language_surface.integration import compile_program, execution_plan_for
from frontend.language_surface.parser import parse
from playground.backend.engine import extract_knowledge, simulate


ROOT = Path(__file__).resolve().parents[2]
SOURCE = """
module Compatibility {
    fn Value() -> int {
        return 42
    }

    calculation Result {
        result = Value()
    }
}
"""


def test_reason_ir_and_execution_plan_remain_schema_compatible() -> None:
    reason_ir, execution_plan, _, _ = _public_artifacts()

    _validate_schema(reason_ir, "reason_ir.schema.json")
    _validate_schema(execution_plan, "execution_plan.schema.json")
    assert reason_ir["schema_version"] == "reason-ir/0.1"
    assert execution_plan["planner_version"] == "language-surface-validation/0.1"


def test_simulation_and_knowledge_interfaces_are_versioned() -> None:
    _, _, simulation, knowledge = _public_artifacts()

    assert simulation["schema_version"] == "semantic-simulation/0.2"
    assert isinstance(simulation["trace"], list)
    assert knowledge["schema_version"] == "knowledge-emergence/0.2"
    assert knowledge["generated_at"] == "1970-01-01T00:00:00+00:00"


def test_public_interface_serialization_is_deterministic() -> None:
    first = _canonical_json(_public_artifacts())
    second = _canonical_json(_public_artifacts())

    assert first == second


def _public_artifacts() -> tuple[dict, dict, dict, dict]:
    reason_ir = compile_program(parse(SOURCE))[0]
    execution_plan = execution_plan_for(reason_ir)
    simulation = simulate(reason_ir)
    knowledge = extract_knowledge(reason_ir, simulation)
    return reason_ir, execution_plan, simulation, knowledge


def _validate_schema(value: dict, schema_name: str) -> None:
    SchemaValidator(ROOT / "schemas").validate_file(value, schema_name)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
