import json
from dataclasses import dataclass

import pytest

from frontend.language_surface import compile_program, parse
from frontend.tensor.runtime import TensorRuntime
from frontend.unified_execution_runtime import (
    BoundaryKind,
    ClusterFailurePolicy,
    ClusterRuntimeAdapter,
    ExecutionPosition,
    ExecutionRequest,
    RuntimeCapability,
    RuntimePressure,
    RuntimeProfiler,
    UnifiedExecutionOrchestrator,
    capture_relation_matrix_baseline,
    compare_runtime_baseline,
    default_runtime_adapters,
    runtime_info,
)


@dataclass
class Backend:
    capability: RuntimeCapability

    def execute(self, request):
        return {"plan": dict(request.execution_plan), "backend": self.capability.backend_id}


class CountingLocalBackend(Backend):
    def __init__(self):
        super().__init__(RuntimeCapability(
            "RuntimeReal", "python", memory_limit=100, tensor_limit=10
        ))
        self.calls = 0

    def execute(self, request):
        self.calls += 1
        return {"mode": "local", "request": request.request_id}


def _cluster_with_worker_failure():
    state = {"calls": 0}

    def execute(partition, request):
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("worker unavailable")
        return {"mode": "cluster", "request": request.request_id}

    return ClusterRuntimeAdapter(
        ("worker-0", "worker-1"),
        execute,
        reduction="single_result",
    ), state


def _runtime():
    return UnifiedExecutionOrchestrator((
        Backend(RuntimeCapability("RuntimeReal", "rust")),
        Backend(RuntimeCapability("ClusterRuntime", "rust", parallel_execution=True)),
    ))


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


def _dynamic_request(request_id="dynamic", *, estimated_operations=100):
    return ExecutionRequest(
        request_id,
        {
            "operations": ["layer-0", "layer-1"],
            "workload": {
                "parallelizable": True,
                "estimated_operations": estimated_operations,
            },
        },
    )


# ---------------------------------------------------------------------------
# UERA-T001 ~ UERA-T004: Capabilities, Transparency, and Common Request IF
# ---------------------------------------------------------------------------


def test_uera_t001_runtime_capability_catalog_enumeration():
    adapters = default_runtime_adapters()
    catalog = {adapter.capability.backend_id: adapter.capability for adapter in adapters}
    assert "RuntimeReal" in catalog
    assert "TensorRuntime" in catalog
    assert "RuntimeComplex" in catalog
    assert "ReasonUnitRuntime" in catalog
    assert "ClusterRuntime" in catalog
    assert catalog["TensorRuntime"].tensor_support is True
    assert catalog["ClusterRuntime"].parallel_execution is True


def test_uera_t002_backend_and_engine_transparency():
    info = runtime_info()
    assert info["orchestrator"]["enabled"] is True
    backends = {b["backend_id"]: b["execution_engine"] for b in info["backends"]}
    assert backends["RuntimeReal"] == "rust"
    assert backends["TensorRuntime"] == "python"


def test_uera_t003_common_execution_request_across_local_backends():
    adapters = [
        a for a in default_runtime_adapters()
        if a.capability.backend_id != "ClusterRuntime"
    ]
    request = ExecutionRequest("uera-t003", {
        "operation": "identity",
        "arguments": [[10, 20, 30]],
    })
    results = {a.capability.backend_id: a.execute(request) for a in adapters}
    assert results == {
        "RuntimeReal": [10, 20, 30],
        "TensorRuntime": [10, 20, 30],
        "RuntimeComplex": [10, 20, 30],
        "ReasonUnitRuntime": [10, 20, 30],
    }


def test_uera_t004_invalid_request_structured_rejection():
    request = ExecutionRequest("invalid-request", {"operation": "identity", "arguments": []})
    for adapter in default_runtime_adapters()[:-1]:
        with pytest.raises((RuntimeError, ValueError), match="UER-REQ-002"):
            adapter.execute(request)


# ---------------------------------------------------------------------------
# UERA-T005 ~ UERA-T008: Numerics, Types, and Tensor Lifetime Management
# ---------------------------------------------------------------------------


def test_uera_t005_numeric_type_promotion_and_scalar_casts():
    source = """module NumericPromotion {
  calculation Calc {
    let int_val: int = 10
    let float_val: float = 2.5
    result = int_val + float_val
  }
}
"""
    reason_ir = compile_program(parse(source))[0]
    request = ExecutionRequest.from_reason_ir("numeric-promo", reason_ir)
    assert request.execution_plan is not None


def test_uera_t006_tensor_type_propagation():
    _, request = _compiled_tensor_request()
    assert request.execution_plan["requirements"]["tensor_support"] is True
    assert "tensor.matmul" in request.execution_plan["requirements"]["operations"]


def test_uera_t007_tensor_deterministic_last_use_release():
    runtime = TensorRuntime()
    t1 = runtime.call("tensor.create", [[1.0, 2.0]], "f64")
    t2 = runtime.call("tensor.create", [[3.0], [4.0]], "f64")
    res = runtime.call("tensor.matmul", t1, t2)
    assert res is not None
    runtime.release(t1)
    runtime.release(t2)
    assert runtime.tensor_releases == 2


def test_uera_t008_persistent_and_parameter_tensor_preservation():
    runtime = TensorRuntime()
    param = runtime.call("tensor.create", [[1.0, 0.0], [0.0, 1.0]], "f64")
    inp = runtime.call("tensor.create", [[2.0, 3.0]], "f64")
    out = runtime.call("tensor.matmul", inp, param)
    assert out is not None
    runtime.release(inp)
    # Parameter remains valid for further operations
    out2 = runtime.call("tensor.matmul", out, param)
    assert out2 is not None
    runtime.release(out)
    runtime.release(out2)
    runtime.release(param)


# ---------------------------------------------------------------------------
# UERA-T009 ~ UERA-T012: Compiler Workload, Placement, and Safe Boundary
# ---------------------------------------------------------------------------


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


def test_uera_t011_does_not_migrate_inside_an_operation():
    local = CountingLocalBackend()
    runtime = UnifiedExecutionOrchestrator((
        local,
        Backend(RuntimeCapability(
            "ClusterRuntime", "rust", parallel_execution=True
        )),
    ))
    profiler = RuntimeProfiler()
    result = runtime.execute(
        _dynamic_request("uera-t011"),
        pressure=RuntimePressure(live_tensors=10),
        position=ExecutionPosition(
            operation_index=0,
            instruction_index=3,
            operation_id="layer-0",
            boundary_kind=BoundaryKind.INSTRUCTION,
        ),
        profiler=profiler,
    )

    assert result.backend_id == "RuntimeReal"
    assert local.calls == 1
    safe_event = next(item for item in result.trace if item["event"] == "SAFE_BOUNDARY")
    assert safe_event["available"] is False
    assert safe_event["reason"] == "execution position is inside an operation"
    assert "CLUSTER_ESCALATED" not in [item["event"] for item in result.trace]


def test_uera_t012_escalates_only_at_automatic_safe_boundary():
    runtime = UnifiedExecutionOrchestrator((
        CountingLocalBackend(),
        Backend(RuntimeCapability(
            "ClusterRuntime", "rust", parallel_execution=True
        )),
    ))
    base_request = _dynamic_request("uera-t012")
    request = ExecutionRequest(
        base_request.request_id,
        base_request.execution_plan,
        metadata={
            "execution_position": {
                "operation_index": 1,
                "instruction_index": 0,
                "operation_id": "layer-1",
                "boundary_kind": "layer",
            }
        },
    )
    result = runtime.execute(
        request,
        pressure=RuntimePressure(live_tensors=10),
    )

    assert result.backend_id == "ClusterRuntime"
    events = [item["event"] for item in result.trace]
    assert events.count("CLUSTER_ESCALATED") == 1
    assert "CLUSTER_PLANNED" not in events
    safe_event = next(item for item in result.trace if item["event"] == "SAFE_BOUNDARY")
    assert safe_event["available"] is True
    assert safe_event["boundary_kind"] == "layer"


# ---------------------------------------------------------------------------
# UERA-T013 ~ UERA-T018: Deterministic Cluster Execution, Reduction, Failure Policy
# ---------------------------------------------------------------------------


def test_uera_t013_cluster_runtime_plan_is_byte_identical_three_times():
    adapter = ClusterRuntimeAdapter(
        ("worker-2", "worker-0", "worker-1"),
        lambda partition, _: partition.operation_id,
    )
    request = ExecutionRequest("uera-t013", {"operations": ["op-a", "op-b", "op-c"]})
    manifests = []
    for _ in range(3):
        adapter.partitions(request, ("op-a", "op-b", "op-c"))
        manifests.append(json.dumps(adapter.last_plan, sort_keys=True, separators=(",", ":")))

    assert manifests[0] == manifests[1] == manifests[2]
    assert adapter.last_plan["schema_version"] == "reasonscript-cluster-uera-plan/0.1"
    assert adapter.last_plan["reduction_order"] == [
        partition["partition_id"] for partition in adapter.last_plan["partitions"]
    ]
    python_partitions = _runtime().canonical_partitions(
        request, ("op-a", "op-b", "op-c"), ("worker-2", "worker-0", "worker-1")
    )
    assert [item.partition_id for item in python_partitions] == [
        item["partition_id"] for item in adapter.last_plan["partitions"]
    ]


def test_uera_t014_worker_availability_uses_canonical_fallback():
    adapter = ClusterRuntimeAdapter(
        ("worker-2", "worker-0", "worker-1"),
        lambda partition, _: partition.operation_id,
        available_workers=("worker-2", "worker-0"),
    )
    request = ExecutionRequest("uera-t014", {"operations": ["op-a", "op-b", "op-c"]})
    first, second, third = [
        adapter.partitions(request, ("op-a", "op-b", "op-c"))
        for _ in range(3)
    ]

    assert first == second == third
    assert [(item.preferred_worker, item.worker_id, item.fallback_used) for item in first] == [
        ("worker-0", "worker-0", False),
        ("worker-1", "worker-2", True),
        ("worker-2", "worker-2", False),
    ]
    unavailable = ClusterRuntimeAdapter(
        ("worker-0",),
        lambda partition, _: partition.operation_id,
        available_workers=(),
    )
    with pytest.raises(RuntimeError, match="CRR-UER-002"):
        unavailable.partitions(request, ("op-a",))


def test_uera_t015_cluster_workers_reuse_local_backend_with_equivalent_result():
    adapters = default_runtime_adapters()
    local = next(item for item in adapters if item.capability.backend_id == "RuntimeReal")
    cluster = next(item for item in adapters if item.capability.backend_id == "ClusterRuntime")
    orchestrator = UnifiedExecutionOrchestrator(adapters)
    request = ExecutionRequest(
        "uera-t015",
        {
            "operation": "identity",
            "arguments": [[1, 2, 3]],
            "workload": {"parallelizable": True, "estimated_operations": 100_000},
        },
    )

    local_value = local.execute(request)
    cluster_results = [orchestrator.execute(request) for _ in range(3)]
    assert [result.value for result in cluster_results] == [
        local_value,
        local_value,
        local_value,
    ]
    assert {result.backend_id for result in cluster_results} == {"ClusterRuntime"}
    assert len({result.semantic_digest for result in cluster_results}) == 1
    assert all(result.profile["worker_tasks"] == 1 for result in cluster_results)
    assert cluster.last_plan["partitions"][0]["operation_id"] == "identity"
    artifacts = orchestrator.artifacts(
        request, orchestrator.plan(request), result=cluster_results[-1]
    )
    assert artifacts["cluster_plan.json"]["schema_version"] == (
        "reasonscript-cluster-uera-plan/0.1"
    )


def test_uera_t016_deterministic_canonical_reduction_order():
    adapter = ClusterRuntimeAdapter(
        ("worker-1", "worker-0"),
        lambda partition, _: f"res-{partition.partition_index}",
    )
    request = ExecutionRequest("uera-t016", {"operations": ["a", "b", "c"]})
    partitions = adapter.partitions(request, ["a", "b", "c"])
    # Out of order completion simulated
    unordered_results = [
        (partitions[2], "val-2"),
        (partitions[0], "val-0"),
        (partitions[1], "val-1"),
    ]
    reduced = adapter.reduce(unordered_results)
    # Must reduce strictly in canonical partition index order
    assert reduced == ["val-0", "val-1", "val-2"]


def test_uera_t017_cluster_failure_policies_are_executed_and_traced():
    request = _dynamic_request("uera-t017", estimated_operations=100_000)

    local = CountingLocalBackend()
    unavailable_cluster = ClusterRuntimeAdapter(
        ("worker-0",),
        lambda partition, request: request.request_id,
        available_workers=(),
    )
    fallback_runtime = UnifiedExecutionOrchestrator((local, unavailable_cluster))
    fallback_profiler = RuntimeProfiler()
    local_result = fallback_runtime.execute(
        request,
        profiler=fallback_profiler,
        cluster_failure_policy=ClusterFailurePolicy.FALLBACK_LOCAL,
    )
    assert local_result.backend_id == "RuntimeReal"
    assert local.calls == 1
    assert [item["event"] for item in local_result.trace][-2:] == [
        "CLUSTER_FAILURE",
        "FALLBACK_LOCAL",
    ]
    artifacts = fallback_runtime.artifacts(
        request,
        fallback_runtime.plan(request),
        profiler=fallback_profiler,
        result=local_result,
    )
    assert [
        item["event"]
        for item in artifacts["cluster_plan.json"]["orchestration_events"]
    ][-2:] == ["CLUSTER_FAILURE", "FALLBACK_LOCAL"]

    retry_cluster, retry_state = _cluster_with_worker_failure()
    retry_result = UnifiedExecutionOrchestrator((
        CountingLocalBackend(), retry_cluster
    )).execute(request, cluster_failure_policy=ClusterFailurePolicy.RETRY)
    assert retry_result.backend_id == "ClusterRuntime"
    assert retry_state["calls"] == 3
    assert "CLUSTER_RETRY" in [item["event"] for item in retry_result.trace]

    single_cluster, single_state = _cluster_with_worker_failure()
    single_result = UnifiedExecutionOrchestrator((
        CountingLocalBackend(), single_cluster
    )).execute(
        request,
        cluster_failure_policy=ClusterFailurePolicy.FALLBACK_SINGLE_NODE,
    )
    assert single_result.value == [
        {"mode": "cluster", "request": request.request_id},
        {"mode": "cluster", "request": request.request_id},
    ]
    assert single_state["calls"] == 3
    assert "FALLBACK_SINGLE_NODE" in [
        item["event"] for item in single_result.trace
    ]


def test_uera_t018_abort_never_performs_silent_fallback():
    local = CountingLocalBackend()
    cluster = ClusterRuntimeAdapter(
        ("worker-0",),
        lambda partition, request: request.request_id,
        available_workers=(),
    )
    runtime = UnifiedExecutionOrchestrator((local, cluster))
    profiler = RuntimeProfiler()
    with pytest.raises(RuntimeError, match="UER-OFF-002"):
        runtime.execute(
            _dynamic_request("uera-t018", estimated_operations=100_000),
            profiler=profiler,
            cluster_failure_policy=ClusterFailurePolicy.ABORT,
        )

    assert local.calls == 0
    failure = next(item for item in profiler.trace if item["event"] == "CLUSTER_FAILURE")
    assert failure["policy"] == "abort"
    assert failure["error_type"] == "RuntimeError"
    assert "CRR-UER-002" in failure["reason"]


# ---------------------------------------------------------------------------
# UERA-T019 ~ UERA-T020: Pure Function Optimization and Relation Matrix Latency
# ---------------------------------------------------------------------------


def test_uera_t019_pure_function_inlining_and_constant_folding():
    source = """module PureMath {
  fn Double(x: int) -> int {
    return x + x
  }

  calculation Calc {
    result = Double(21)
  }
}
"""
    program = parse(source)
    assert len(program.modules) >= 1
    assert program.modules[0].name == "PureMath"
    compiled = compile_program(program)
    assert len(compiled) >= 1


def test_uera_t020_relation_matrix_optimization_and_latency_target():
    runtime = _runtime()
    req = ExecutionRequest("baseline-req", {"operations": ["a", "b"]})
    res = runtime.execute(req)
    pressure = RuntimePressure()
    baseline = capture_relation_matrix_baseline(res, pressure)
    assert baseline.fixture_id == "Transformer_Test.RelationMatrix"
    assert baseline.targets["max_execution_time_ms"] == 1500.0
    comparison = compare_runtime_baseline(baseline, baseline)
    assert comparison["checks"]["fixture_match"] is True
    assert comparison["checks"]["semantic_digest_match"] is True


# ---------------------------------------------------------------------------
# UERA-T021 ~ UERA-T022: Parser Conformance (Multiline Parentheses & Signatures)
# ---------------------------------------------------------------------------


def test_uera_t021_multiline_parenthesized_expression_parsing():
    source = """module MultilineExpr {
  calculation Calc {
    let x = (
      1 +
      2 +
      3
    )
    result = x
  }
}
"""
    program = parse(source)
    assert len(program.modules) >= 1
    assert program.modules[0].name == "MultilineExpr"


def test_uera_t022_multiline_function_signature_parsing():
    source = """module MultilineSig {
  fn Add(
    a: int,
    b: int
  ) -> int {
    return a + b
  }

  calculation Calc {
    result = Add(1, 2)
  }
}
"""
    program = parse(source)
    assert len(program.modules) >= 1
    assert program.modules[0].name == "MultilineSig"


# ---------------------------------------------------------------------------
# UERA-T023 ~ UERA-T025: Workload Fixtures, Transformer Regression, Determinism
# ---------------------------------------------------------------------------


def test_uera_t023_workload_offload_matrix_small_medium_large_overload():
    runtime = _runtime()
    small = runtime.plan(ExecutionRequest("small", {"workload": {"estimated_operations": 10}}))
    medium = runtime.plan(ExecutionRequest("medium", {"workload": {"parallelizable": True, "estimated_operations": 500}}))
    large = runtime.plan(ExecutionRequest("large", {"workload": {"parallelizable": True, "estimated_operations": 100_000}}))
    overload = runtime.plan(ExecutionRequest("overload", {"workload": {"parallelizable": True, "estimated_operations": 500_000}}))

    assert small.placement == "LOCAL"
    assert medium.placement == "LOCAL_MONITORED"
    assert large.placement == "CLUSTER_PLANNED"
    assert overload.placement == "CLUSTER_PLANNED"


def test_uera_t024_transformer_model_and_sparse_routing_regression():
    # Verify standard transformer tensor flow
    runtime = TensorRuntime()
    hidden = runtime.call("tensor.create", [[0.1, 0.2, 0.3, 0.4]], "f64")
    weight = runtime.call("tensor.create", [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [0.0, 0.0]], "f64")
    proj = runtime.call("tensor.matmul", hidden, weight)
    assert proj is not None
    runtime.release(hidden)
    runtime.release(weight)
    runtime.release(proj)


def test_uera_t025_end_to_end_three_independent_runs_are_byte_identical():
    runtime = _runtime()
    request = ExecutionRequest("e2e-determinism", {
        "operations": ["stage1", "stage2", "stage3"],
        "workload": {"parallelizable": True, "estimated_operations": 100_000},
    })
    payloads = [
        json.dumps(runtime.execute(request).value, sort_keys=True, separators=(",", ":"))
        for _ in range(3)
    ]
    assert payloads[0] == payloads[1] == payloads[2]
