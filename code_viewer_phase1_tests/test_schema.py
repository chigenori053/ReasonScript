from __future__ import annotations

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

from toolchain.code_viewer import Stage, project, to_json_value

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "code_viewer_document.schema.json").read_text(encoding="utf-8"))
DEPENDENCY_SOURCE = ROOT / "examples" / "v0_5" / "003_calculation_dependency.rsn"


def test_valid_source_document_matches_schema():
    source = DEPENDENCY_SOURCE.read_text(encoding="utf-8")
    document = project(source, DEPENDENCY_SOURCE)
    jsonschema.validate(to_json_value(document), SCHEMA)


def test_degraded_document_with_diagnostics_matches_schema():
    source = "module Broken {\n  calculation X {\n    result = \n  }\n}\n"
    document = project(source, Path("broken.rsn"))
    assert document.stages[Stage.SURFACE].diagnostics  # exercise the diagnostic branch
    jsonschema.validate(to_json_value(document), SCHEMA)
