import json
from dataclasses import dataclass

import pytest

from frontend.language_surface import compile_program, parse
from frontend.unified_execution_runtime import ExecutionRequest, RuntimeCapability, UnifiedExecutionOrchestrator, default_runtime_adapters


@dataclass
class Backend:
    capability: RuntimeCapability

    def execute(self, request):
        return {"plan": dict(request.execution_plan), "backend": self.capability.backend_id}


def _runtime():
    return UnifiedExecutionOrchestrator((
        Backend(RuntimeCapability("RuntimeReal", "rust")),
        Backend(RuntimeCapability("ClusterRuntime", "rust", parallel_execution=True)),
    ))


def test_offload_validation_matrix():
    runtime = _runtime()
    small = runtime.plan(ExecutionRequest("small", {"workload": {}}))
    medium = runtime.plan(ExecutionRequest("medium", {"workload": {"parallelizable": True}}))
    large = runtime.plan(ExecutionRequest("large", {"workload": {"parallelizable": True, "estimated_operations": 100_000}}))
    assert small.placement == "LOCAL"
    assert medium.placement == "LOCAL_MONITORED"
    assert large.placement == "CLUSTER_PLANNED"


def test_three_independent_runs_are_byte_identical():
    runtime = _runtime()
    request = ExecutionRequest("deterministic", {"operations": ["a", "b"]})
    payloads = [json.dumps(runtime.execute(request).value, sort_keys=True, separators=(",", ":")) for _ in range(3)]
    assert payloads[0] == payloads[1] == payloads[2]


TENSOR_SOURCE = """module Placement {
  calculation Matrix {
    let left = tensor.create([[1.0, 2.0]], "f64")
    let right = tensor.create([[1.0], [2.0]], "f64")
    result = tensor.matmul(left, right)
  }
}
"""


def _compiled_tensor_request():
    reason_ir = compile_program(parse(TENSOR_SOURCE))[0]
    return reason_ir, ExecutionRequest.from_reason_ir("compiled-tensor", reason_ir)


def test_uera_t009_compiler_transfers_workload_and_capability_requirements():
    _, request = _compiled_tensor_request()
    workload = request.execution_plan["workload"]
    requirements = request.execution_plan["requirements"]

    assert workload == {
        "estimated_operations": 8,
        "estimated_memory": 40,
        "estimated_peak_live_tensors": 3,
        "estimated_autograd_nodes": 0,
        "parallelizable": True,
        "dependency_depth": 2,
        "transfer_cost": 40,
        "estimator_version": "reason-ir-workload/0.1",
    }
    assert requirements["tensor_support"] is True
    assert requirements["operations"] == [
        "tensor.create",
        "tensor.matmul",
    ]
    serialized = json.dumps(request.execution_plan, sort_keys=True)
    assert "RuntimeReal" not in serialized
    assert "TensorRuntime" not in serialized
    assert "ClusterRuntime" not in serialized


def test_uera_t010_compiled_plan_selects_executor_and_records_reason():
    _, request = _compiled_tensor_request()
    runtime = UnifiedExecutionOrchestrator((
        Backend(RuntimeCapability("RuntimeReal", "rust")),
        Backend(RuntimeCapability(
            "TensorRuntime",
            "python",
            tensor_support=True,
            numeric_types=("Int", "Float"),
        )),
        Backend(RuntimeCapability(
            "ClusterRuntime", "rust", parallel_execution=True
        )),
    ))

    medium = runtime.plan(request)
    assert (medium.placement, medium.backend_id) == (
        "LOCAL_MONITORED",
        "TensorRuntime",
    )
    result = runtime.execute(request)
    assert result.backend_id == "TensorRuntime"
    assert result.value["backend"] == "TensorRuntime"
    assert UnifiedExecutionOrchestrator(default_runtime_adapters()).plan(
        request
    ).backend_id == "TensorRuntime"
    artifacts = runtime.artifacts(request, medium, result=result)
    assert artifacts["execution_plan.json"]["placement_decision"]["reason"] == (
        "local-first policy"
    )

    large_plan = dict(request.execution_plan)
    large_plan["workload"] = {
        **large_plan["workload"],
        "estimated_operations": 100_000,
    }
    large = runtime.plan(ExecutionRequest("large-compiled", large_plan))
    assert (large.placement, large.backend_id) == (
        "CLUSTER_PLANNED",
        "ClusterRuntime",
    )
    assert large.reason == "parallel workload exceeds planned-offload threshold"

    with pytest.raises(ValueError, match="UER-CAP-003"):
        runtime.plan(request, preferred_backend="RuntimeReal")

    scalar_ir = compile_program(parse("""module Scalar {
      calculation Answer {
        result = 1 + 2
      }
    }
    """))[0]
    small = runtime.plan(ExecutionRequest.from_reason_ir("compiled-scalar", scalar_ir))
    assert (small.placement, small.backend_id) == ("LOCAL", "RuntimeReal")
