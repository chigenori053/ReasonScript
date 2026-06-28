import json
from pathlib import Path

from frontend.language_surface.integration import compile_program
from frontend.language_surface.parser import parse
from playground.backend.engine import build_execution_plan, extract_knowledge, simulate


ROOT = Path(__file__).resolve().parents[2]


def _pipeline(source: str):
    ir = compile_program(parse(source))[0]
    simulation = simulate(ir)
    return {
        "ir": ir,
        "plan": build_execution_plan(ir),
        "simulation": simulation,
        "knowledge": extract_knowledge(ir, simulation),
    }


def test_language_surface_v0_5_deliverables_exist_and_matrix_passes():
    deliverables = [
        "docs/specs/reasonscript_language_surface_v0_5.md",
        "CHANGELOG.md",
        "RELEASE_NOTES_v0_5.md",
        "playground_language_surface_v0_5_audit.md",
        "playground_language_surface_v0_5_matrix.json",
    ]
    for relative in deliverables:
        assert (ROOT / relative).exists(), relative

    matrix = json.loads((ROOT / "playground_language_surface_v0_5_matrix.json").read_text())
    assert matrix["specification"] == "reasonscript-language-surface/0.5"
    assert matrix["feature_freeze"] == {
        "syntax": "frozen",
        "semantic_lowering": "frozen",
        "public_interfaces": "frozen",
        "canonical_paths": "frozen",
        "pattern_identity": "frozen",
    }
    assert all(item["status"] == "PASS" for item in matrix["coverage"])


def test_language_surface_v0_5_pattern_pipeline_is_deterministic():
    source = """
    module Freeze {
        struct Point {
            x: int
            y: int
        }

        fn RangeScore(score: int, passed: bool) -> int {
            match score {
                0..49 => return 0
                50..<80 => return 1
                80..100 when passed => return 2
                default => return 3
            }
        }

        fn ShapeScore(point: Point) -> int {
            match point {
                Point { x: 0, y } => return y
                Point { x: 1, y: 1 } => return 1
                default => return 0
            }
        }

        fn OrScore(score: int) -> int {
            match score {
                0..10 | 90..100 => return 1
                default => return 0
            }
        }

        calculation Result {
            let a = RangeScore(85, true)
            let b = ShapeScore(Point { x: 0, y: 7 })
            result = OrScore(95)
        }
    }
    """

    first = _pipeline(source)
    second = _pipeline(source)

    assert first["plan"]["selected_branch"] == "RangeScore.match.range.80_100|guard.passed"
    assert first["plan"]["pattern_identity"] == {
        "pattern_id": "RangeScore.match.range.80_100|guard.passed",
        "pattern_type": "Guard",
        "canonical_path": "RangeScore.match.range.80_100|guard.passed",
    }
    assert first["plan"]["pattern_identity"] == second["plan"]["pattern_identity"]
    assert first["simulation"]["pattern_identity"] == first["plan"]["pattern_identity"]
    assert first["knowledge"]["knowledge"][0]["pattern_identity"] == first["plan"]["pattern_identity"]
    assert json.dumps(first["ir"]["metadata"]["function_ir"], sort_keys=True) == json.dumps(
        second["ir"]["metadata"]["function_ir"],
        sort_keys=True,
    )


def test_language_surface_v0_5_public_interface_freeze_is_documented():
    spec = (ROOT / "docs/specs/reasonscript_language_surface_v0_5.md").read_text()
    for interface in [
        "reasonscript-language-surface/0.5",
        "parser/0.5",
        "reasonscript-ast/0.5",
        "reason-ir/0.5",
        "execution-plan/0.5",
    ]:
        assert interface in spec

    assert "Pattern Alias" in spec
    assert "Tuple Pattern" in spec
    assert "Array Pattern" in spec
    assert "Map Pattern" in spec
    assert "v0.6" in spec
