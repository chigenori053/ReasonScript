import json
from pathlib import Path

from scripts.benchmark_executable_ru import CASES, fixed_cases, source_for, validate_cases
from frontend.computation_ir import lower_program
from frontend.language_surface import parse


def test_executable_ru_dataset_is_fixed_complete_and_parseable():
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    validate_cases(cases)
    assert cases == fixed_cases()
    assert {case["test_id"] for case in cases} >= {
        "highly_composite_24b",
        "synthetic_sqrt1000000_k6",
        "synthetic_sqrt1000000_k8",
    }
    for case in cases:
        assert lower_program(parse(source_for(case)))["calculations"] == ["Answer"]


def test_executable_ru_benchmark_has_six_graph_definitions():
    source = (Path(__file__).parents[1] / "scripts/benchmark_executable_ru.py").read_text()
    assert source.count(".svg\"") == 6
