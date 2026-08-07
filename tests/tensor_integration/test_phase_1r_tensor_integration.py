from __future__ import annotations

import json
from pathlib import Path

import pytest

from frontend.integrated_computation_runtime import LoopLimitError, execute_program
from frontend.language_surface import compile_program, parse, project_program
from frontend.tensor import TensorError, TensorPolicy, TensorRuntime
from frontend.tensor.integration import (
    public_registry,
    tensor_execution_plan,
    tensor_operations,
)
from toolchain.project_validation import validate_project

ROOT = Path(__file__).resolve().parents[2]
TENSOR_PROBE = ROOT / "tests" / "fixtures" / "tensor_integration_probe.rsn"
LOOP_PROBE = ROOT / "tests" / "fixtures" / "iterative_state_probe.rsn"
STANDALONE = ROOT / "tests" / "fixtures" / "standalone_project"


def _program(path: Path):
    return parse(path.read_text(encoding="utf-8"))


def test_tensor_namespace_registry_and_semantic_contract_are_public():
    program = _program(TENSOR_PROBE)
    project_program(program)
    registry = {entry["qualified_name"]: entry for entry in public_registry()}
    assert {"tensor.create", "tensor.relu", "tensor.softmax", "tensor.linear"} <= registry.keys()
    assert all(entry["callable"] and entry["deterministic"] for entry in registry.values())
    assert registry["tensor.linear"]["lowering_policy"] == "primitive_or_native"


def test_tensor_named_arguments_are_accepted_and_duplicates_rejected():
    valid = parse(
        """
        module NamedTensorArguments {
          calculation Answer {
            let input = tensor.create([[1.0, 2.0]], dtype = "f64")
            result = tensor.softmax(input, axis = -1)
          }
        }
        """
    )
    assert execute_program(valid).to_dict()["result"][0] == pytest.approx([0.2689414214, 0.7310585786])
    with pytest.raises(Exception, match="TSF-016 duplicate Tensor argument"):
        parse(
            """
            module DuplicateTensorArgument {
              calculation Answer {
                result = tensor.create([1.0], dtype = "f64", dtype = "f32")
              }
            }
            """
        )


def test_reason_ir_and_execution_plan_keep_tensor_traceability():
    program = _program(TENSOR_PROBE)
    reason_ir = compile_program(program)[0]
    operations = reason_ir["metadata"]["tensor_operations"]
    assert [item["function"] for item in operations] == [
        "tensor.create",
        "tensor.create",
        "tensor.create",
        "tensor.linear",
        "tensor.relu",
        "tensor.softmax",
    ]
    assert [item["operation_id"] for item in operations] == [f"tensor_call_{i:03d}" for i in range(1, 7)]
    assert operations[3]["tensor_metadata"]["shape"] == [1, 2]
    assert operations[3]["lowered_operations"] == ["tensor.matmul", "tensor.add"]
    assert "source_ref" in operations[0]
    plan = reason_ir["metadata"]["tensor_execution_plan"]
    assert [item["execution_order"] for item in plan["operations"]] == list(range(1, 7))
    assert plan["backend"] == "abstract"
    assert json.dumps(plan, sort_keys=True) == json.dumps(
        tensor_execution_plan(tensor_operations(program.modules[0])), sort_keys=True
    )


def test_inference_probe_matches_reference_and_is_deterministic():
    payloads = [execute_program(_program(TENSOR_PROBE)).to_dict() for _ in range(3)]
    assert payloads[0] == payloads[1] == payloads[2]
    assert payloads[0]["result"][0] == pytest.approx([0.5, 0.5])
    assert sum(payloads[0]["result"][0]) == pytest.approx(1.0, abs=1e-12)
    assert payloads[0]["tensor_metadata"][-1]["shape"] == [1, 2]
    trace = payloads[0]["tensor_trace"]
    assert trace[-3]["semantic_operation"] == "tensor.linear"
    assert trace[-3]["lowered_operations"] == ["tensor.matmul", "tensor.add"]


@pytest.mark.parametrize(
    "action,code",
    [
        (lambda runtime: runtime.create([]), "TSF-009"),
        (lambda runtime: runtime.create([[]]), "TSF-009"),
        (lambda runtime: runtime.create([float("nan")]), "TSF-010"),
        (lambda runtime: runtime.create([float("inf")]), "TSF-011"),
        (lambda runtime: runtime.create([float("-inf")]), "TSF-011"),
        (lambda runtime: runtime.call("tensor.exp", runtime.create([1000.0])), "TSF-012"),
    ],
)
def test_invalid_tensor_probe_returns_stable_diagnostics(action, code):
    with pytest.raises(TensorError) as captured:
        action(TensorRuntime())
    diagnostic = captured.value.diagnostic.to_dict()
    assert diagnostic["code"] == code
    assert diagnostic["severity"] == "fatal"
    assert "Traceback" not in diagnostic["message"]


def test_external_tensor_artifact_is_checksum_and_value_validated(tmp_path: Path):
    writer = TensorRuntime(policy=TensorPolicy(inline_elements=0))
    value = writer.create([1.0, 2.0, 3.0])
    metadata = writer.artifact(value, tmp_path)
    loaded = TensorRuntime().load_artifact(metadata)
    assert loaded.shape == (3,)
    metadata["checksum"] = "sha256:" + "0" * 64
    with pytest.raises(TensorError, match="checksum mismatch"):
        TensorRuntime().load_artifact(metadata)


def test_iterative_state_probe_and_loop_limit():
    result = execute_program(_program(LOOP_PROBE)).to_dict()
    assert result["result"] == pytest.approx(4.463129088)
    assert len(result["loop_trace"]) == 10
    assert [item["iteration"] for item in result["loop_trace"]] == list(range(1, 11))

    infinite = parse(
        """
        module Infinite {
          calculation Answer {
            loop {
              continue
            }
            result = 0
          }
        }
        """
    )
    with pytest.raises(LoopLimitError):
        execute_program(infinite, max_loop_iterations=3)


def test_tensor_iteration_releases_overwritten_values_and_traces_metadata_only():
    row = "[" + ", ".join(["0.0"] * 20) + "]"
    matrix = "[" + ", ".join([row] * 20) + "]"
    program = parse(
        f"""
        module TensorIterationStress {{
          calculation Answer {{
            let iteration = 0
            let value = tensor.create({matrix})
            while iteration < 1100 {{
              value = tensor.relu(value)
              iteration = iteration + 1
            }}
            result = iteration
          }}
        }}
        """
    )

    executed = execute_program(program, max_loop_iterations=1200)
    payload = executed.to_dict()

    assert payload["result"] == 1100
    assert len(payload["loop_trace"]) == 1100
    assert (
        payload["loop_trace"][0]["previous_state"]["value"]["metadata"]["shape"]
        == [20, 20]
    )
    assert executed.runtime._refs == {}


def test_runtime_tensor_diagnostic_includes_call_source_location():
    program = parse(
        """module InvalidTensor {
  calculation Answer {
    let values = []
    result = tensor.create(values)
  }
}
"""
    )

    with pytest.raises(TensorError) as captured:
        execute_program(program)

    assert captured.value.diagnostic.to_dict()["source_location"] == {
        "line": 4,
        "column": 14,
    }


def test_standalone_project_validation_does_not_require_repository_workflow():
    report = validate_project(STANDALONE)
    assert report["status"] == "passed"
    assert report["repository_workflow_required"] is False
    assert report["sources_passed"] == report["sources_total"] == 1
    assert report["determinism_passed"] is True
    assert not (STANDALONE / ".github" / "workflows").exists()
