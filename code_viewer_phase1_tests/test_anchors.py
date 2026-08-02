from __future__ import annotations

from toolchain.code_viewer.anchors import scan_anchors


SOURCE = """module CalculationDependency {
  calculation Base {
    result = 21
  }

  calculation Answer {
    result = Base * 2
  }
}
"""


def test_scan_anchors_finds_module_and_calculations():
    anchors = {a.symbol: a for a in scan_anchors(SOURCE)}
    assert set(anchors) == {"CalculationDependency", "Base", "Answer"}
    assert anchors["CalculationDependency"].kind == "module"
    assert anchors["CalculationDependency"].source_line == 1
    assert anchors["CalculationDependency"].source_end_line == 9
    assert anchors["Base"].kind == "calculation"
    assert anchors["Base"].source_line == 2
    assert anchors["Base"].source_end_line == 4
    assert anchors["Answer"].source_line == 6
    assert anchors["Answer"].source_end_line == 8


def test_scan_anchors_survives_blank_lines_and_comments():
    source = (
        "module M {\n"
        "\n"
        "  // a leading comment\n"
        "  calculation Base {\n"
        "    result = 1\n"
        "  }\n"
        "}\n"
    )
    anchors = {a.symbol: a for a in scan_anchors(source)}
    assert anchors["Base"].source_line == 4
    assert anchors["Base"].source_end_line == 6


def test_scan_anchors_works_on_syntactically_invalid_source():
    # Missing closing brace for the module — a real parser would raise, but
    # the lexical scan must still index what it can find (design doc §9).
    source = "module M {\n  calculation Base {\n    result = 1\n  }\n"
    anchors = {a.symbol: a for a in scan_anchors(source)}
    assert "Base" in anchors
    assert "M" not in anchors  # module's own brace never closes


def test_scan_anchors_indexes_struct_enum_and_function():
    source = (
        "module M {\n"
        "  struct Point { x: Int, y: Int }\n"
        "  enum Direction {\n"
        "    North\n"
        "  }\n"
        "  fn double(value: Int): Int {\n"
        "    return value\n"
        "  }\n"
        "}\n"
    )
    anchors = {a.symbol: a for a in scan_anchors(source)}
    assert anchors["Point"].kind == "struct"
    assert anchors["Direction"].kind == "enum"
    assert anchors["double"].kind == "function"
