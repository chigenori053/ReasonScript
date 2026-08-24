"""Phase 6 gate: native reasoning results, traces, and backend provenance."""

from __future__ import annotations

from pathlib import Path

import pytest

from frontend.computation_ir import interpret_program, lower_program, validate_program
from frontend.computation_ir.optimizer import optimize_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import IntegratedRuntimeError, execute_program
from frontend.language_surface import parse
from toolchain.runtime_dispatch import unsupported_rust_operations


BINARY = find_binary()
pytestmark = pytest.mark.skipif(BINARY is None, reason="Rust runtime host is not built")

SOURCE = '''module Reasoning {
  calculation Search {
    result = runtime.search("Goal")
  }
  calculation Simulate {
    result = runtime.simulate("Plan")
  }
  calculation Predict {
    result = runtime.predict("State")
  }
  calculation Plan {
    result = runtime.plan("Goal")
  }
}'''


def test_all_reasoning_operations_match_both_python_references_and_rust() -> None:
    program = parse(SOURCE)
    ir = lower_program(program)
    assert validate_program(ir) == []
    ast = execute_program(program).to_dict()
    interpreter = interpret_program(ir).to_dict()
    rust = run_ir(ir, binary=BINARY, trace_enabled=True)

    assert rust.ok, (rust.error_code, rust.error_message)
    assert ast["calculations"] == interpreter["calculations"] == rust.calculation_results
    assert ast["reasoning_trace"] == interpreter["reasoning_trace"]
    assert rust.metadata["reasoning_trace"] == ast["reasoning_trace"]
    assert unsupported_rust_operations(ir) == ()


def test_reasoning_declaration_bindings_lower_and_execute() -> None:
    source = '''module Route {
  goal Destination {
    description: Reach destination
  }
  state Start {
    label: Origin
  }
  state End {
    label: Destination
  }
  execution_plan RoutePlan {
    step Start -> End
  }
  fn Find() {
    return runtime.search(Destination)
  }
  calculation Search {
    result = Find()
  }
  calculation Simulate {
    result = runtime.simulate(RoutePlan)
  }
  calculation Predict {
    result = runtime.predict(Start)
  }
}'''
    program = parse(source)
    ir = lower_program(program)
    assert ir["reasoning_bindings"] == {
        "Destination": "Destination",
        "End": "End",
        "RoutePlan": "RoutePlan",
        "Start": "Start",
    }
    rust = run_ir(ir, binary=BINARY)
    assert rust.ok, (rust.error_code, rust.error_message)
    assert rust.calculation_results == execute_program(program).to_dict()["calculations"]


def test_manifest_backend_selects_native_engine_without_changing_result() -> None:
    ir = lower_program(parse(SOURCE))
    real = run_ir(ir, binary=BINARY, backend="RuntimeReal", trace_enabled=True)
    hybrid = run_ir(ir, binary=BINARY, backend="HybridRuntime", trace_enabled=True)
    assert real.ok and hybrid.ok
    assert real.calculation_results == hybrid.calculation_results
    assert real.metadata["reasoning_trace"][0]["engine"] == "RuntimeReal SearchEngine"
    assert hybrid.metadata["reasoning_trace"][0]["engine"] == "HybridRuntime SearchEngine"


def test_reasoning_conversion_error_code_matches_python_references() -> None:
    source = '''module Invalid {
  calculation Search {
    result = runtime.search("not a goal")
  }
}'''
    program = parse(source)
    ir = lower_program(program)
    with pytest.raises(IntegratedRuntimeError) as ast:
        execute_program(program)
    with pytest.raises(IntegratedRuntimeError) as interpreter:
        interpret_program(ir)
    rust = run_ir(ir, binary=BINARY)
    assert ast.value.code == interpreter.value.code == rust.error_code == "ReasoningTypeConversionFailed"


def test_reasoning_source_uses_rust_first_production_dispatch(tmp_path: Path) -> None:
    from scripts.reason_cli import _run_result

    source = tmp_path / "reasoning.rsn"
    source.write_text(SOURCE, encoding="utf-8")
    result = _run_result(source, "normal", include_trace=True)
    assert result["ok"]
    assert result["execution_mode"] == "integrated-rust"
    assert [item["operation"] for item in result["runtime_result"]["reasoning_trace"]] == [
        "runtime.search",
        "runtime.simulate",
        "runtime.predict",
        "runtime.plan",
    ]


def test_ir_optimizer_preserves_observable_reasoning_calls() -> None:
    ir = lower_program(parse(SOURCE))
    optimized = optimize_program(ir)
    assert validate_program(optimized) == []
    original = run_ir(ir, binary=BINARY, trace_enabled=True)
    result = run_ir(optimized, binary=BINARY, trace_enabled=True)
    assert result.ok and original.ok
    assert result.calculation_results == original.calculation_results
    assert result.metadata["reasoning_trace"] == original.metadata["reasoning_trace"]
