from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from frontend.ast import to_json_value as semantic_to_json_value
from frontend.language_surface.integration import compile_program, project_program
from frontend.language_surface.nodes import to_json_value as surface_to_json_value
from frontend.language_surface.parser import parse
from playground.backend.engine import build_execution_plan, extract_knowledge, simulate


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests" / "fixtures" / "test_platform" / "sample001.rsn"
GOLDEN = ROOT / "golden" / "sample001"


def test_sample001_pipeline_matches_golden_artifacts() -> None:
    outputs = _pipeline(SOURCE.read_text())
    for name, output in outputs.items():
        expected = json.loads((GOLDEN / f"sample001.{name}.json").read_text())
        assert output == expected, name


def _pipeline(source: str) -> dict[str, Any]:
    program = parse(source)
    semantic = semantic_to_json_value(project_program(program)[0])
    ir = compile_program(program)[0]
    simulation = simulate(ir)
    return {
        "ast": surface_to_json_value(program),
        "semantic": semantic,
        "reason_ir": ir,
        "execution": build_execution_plan(ir),
        "simulation": simulation,
        "knowledge": extract_knowledge(ir, simulation),
    }
