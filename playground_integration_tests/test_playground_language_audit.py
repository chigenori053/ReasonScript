from pathlib import Path

from frontend.ast import to_json_value as semantic_to_json_value
from frontend.language_surface.integration import compile_program, project_program
from frontend.language_surface.parser import parse
from playground.backend.language_audit import run_language_audit, write_language_audit_reports


def test_function_arrow_return_type_projects_and_lowers():
    source = """module Basic {
  fn Value() -> int {
    return 42
  }
}
"""

    program = parse(source)
    semantic_ast = [semantic_to_json_value(module) for module in project_program(program)]
    reason_irs = list(compile_program(program))

    assert program.modules[0].body[0].name == "Value"
    assert semantic_ast[0]["node_type"] == "ModuleNode"
    assert reason_irs[0]["metadata"]["function_declarations"][0]["name"] == "Value"


def test_language_audit_matrix_is_fully_connected():
    matrix = run_language_audit()

    assert matrix["summary"] == {
        "total": 31,
        "connected": 31,
        "partial": 0,
        "missing": 0,
        "broken": 0,
        "connected_pct": 100.0,
    }
    assert {row["status"] for row in matrix["features"]} == {"CONNECTED"}


def test_language_audit_reports_are_exportable(tmp_path: Path):
    files = write_language_audit_reports(tmp_path)

    for path in files.values():
        assert Path(path).exists()
        assert Path(path).read_text(encoding="utf-8").strip()
