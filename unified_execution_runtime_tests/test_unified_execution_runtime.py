from dataclasses import dataclass

from frontend.tensor.runtime import TensorRuntime
from frontend.unified_execution_runtime import (
    ClusterFailurePolicy, ClusterRuntimeAdapter, ExecutionRequest, RuntimeBaseline, RuntimeCapability, RuntimePressure, RuntimeProfiler, UnifiedExecutionOrchestrator,
    WorkloadEstimate, WorkloadEstimator,
    capture_relation_matrix_baseline,
    compare_runtime_baseline,
    default_runtime_adapters,
    runtime_info,
)


@dataclass
class Backend:
    capability: RuntimeCapability
    def execute(self, request):
        return {"request": request.request_id, "backend": self.capability.backend_id}


def _orchestrator():
    return UnifiedExecutionOrchestrator([
        Backend(RuntimeCapability("RuntimeReal", "python", memory_limit=100, tensor_limit=10)),
        Backend(RuntimeCapability("ClusterRuntime", "rust", parallel_execution=True, memory_limit=1_000, tensor_limit=100)),
    ])


def test_local_first_and_planned_offload():
    runtime = _orchestrator()
    local = runtime.plan(ExecutionRequest("small", {"id": 1}))
    assert local.placement == "LOCAL"
    large = runtime.plan(ExecutionRequest("large", {"id": 2}, WorkloadEstimate(estimated_operations=100_000, parallelizable=True)))
    assert (large.placement, large.backend_id) == ("CLUSTER_PLANNED", "ClusterRuntime")


def test_escalation_requires_safe_boundary():
    runtime = _orchestrator()
    decision = runtime.plan(ExecutionRequest(
        "r", {"operations": ["a"], "workload": {"parallelizable": True}}
    ))
    pressure = RuntimePressure(live_tensors=10)
    assert runtime.escalate(
        decision, pressure, safe_boundary=False
    ).placement == "LOCAL_MONITORED"
    assert runtime.escalate(decision, pressure, safe_boundary=True).placement == "CLUSTER_ESCALATED"


def test_partitions_are_canonical_and_artifacts_are_explicit():
    runtime = _orchestrator()
    request = ExecutionRequest("r", {"operations": ["a", "b"]})
    first = runtime.canonical_partitions(request, ["a", "b"], ["w1", "w0"])
    second = runtime.canonical_partitions(request, ["a", "b"], ["w0", "w1"])
    assert first == second
    artifacts = runtime.artifacts(request, runtime.plan(request))
    assert artifacts["cluster_plan.json"]["used"] is False


def test_default_runtime_catalog_is_backend_transparent():
    catalog = {item.capability.backend_id: item.capability for item in default_runtime_adapters()}
    assert catalog["TensorRuntime"].execution_engine == "python"
    assert catalog["RuntimeReal"].execution_engine == "rust"
    assert runtime_info()["orchestrator"]["enabled"] is True


def test_all_local_runtime_adapters_execute_the_same_request_consistently():
    adapters = [
        adapter for adapter in default_runtime_adapters()
        if adapter.capability.backend_id != "ClusterRuntime"
    ]
    request = ExecutionRequest("adapter-parity", {
        "operation": "identity",
        "arguments": [[1, 2, 3]],
    })
    results = {
        adapter.capability.backend_id: adapter.execute(request)
        for adapter in adapters
    }
    assert results == {
        "RuntimeReal": [1, 2, 3],
        "TensorRuntime": [1, 2, 3],
        "RuntimeComplex": [1, 2, 3],
        "ReasonUnitRuntime": [1, 2, 3],
    }


def test_local_runtime_adapters_reject_an_invalid_common_request():
    request = ExecutionRequest("invalid", {"operation": "identity", "arguments": []})
    for adapter in default_runtime_adapters()[:-1]:
        try:
            adapter.execute(request)
        except (RuntimeError, ValueError) as error:
            assert "UER-REQ-002" in str(error)
        else:
            raise AssertionError(f"{adapter.capability.backend_id} accepted an invalid request")


def test_profiler_and_artifacts_record_trace_and_pressure():
    runtime = _orchestrator()
    request = ExecutionRequest("profiled", {"id": 1})
    profiler = RuntimeProfiler()
    result = runtime.execute(request, profiler=profiler)
    artifacts = runtime.artifacts(request, runtime.plan(request), RuntimePressure(live_tensors=3), profiler, result)
    assert artifacts["execution_trace.json"][0]["event"] == "LOCAL"
    assert artifacts["runtime_profile.json"]["peak_live_tensors"] == 3
    assert artifacts["execution_result.json"]["request_id"] == "profiled"


def test_workload_estimator_reads_execution_plan_metadata():
    estimate = WorkloadEstimator.from_plan({"steps": [1, 2], "workload": {"parallelizable": True, "estimated_memory": 64}})
    assert estimate.estimated_operations == 2
    assert estimate.parallelizable is True


def test_orchestrator_uses_execution_plan_workload_for_placement():
    runtime = _orchestrator()
    request = ExecutionRequest("large", {"workload": {"estimated_operations": 100_000, "parallelizable": True}})
    decision = runtime.plan(request)
    assert (decision.placement, decision.backend_id) == ("CLUSTER_PLANNED", "ClusterRuntime")


def test_cluster_adapter_reduces_in_canonical_not_completion_order():
    adapter = ClusterRuntimeAdapter(("worker-1", "worker-0"), lambda partition, _: f"result-{partition.partition_index}")
    request = ExecutionRequest("cluster", {"operations": ["a", "b", "c"]})
    partitions = adapter.partitions(request, ["a", "b", "c"])
    completed = [(partitions[2], "result-2"), (partitions[0], "result-0"), (partitions[1], "result-1")]
    assert adapter.reduce(completed) == ["result-0", "result-1", "result-2"]


def test_cluster_failure_uses_declared_and_traced_fallback_policy():
    runtime = _orchestrator()
    request = ExecutionRequest("failure", {"id": 1})
    profiler = RuntimeProfiler()
    result = runtime.handle_cluster_failure(request, runtime.plan(request), ClusterFailurePolicy.FALLBACK_LOCAL, profiler)
    assert result.placement == "FALLBACK_LOCAL"
    assert [item["event"] for item in profiler.trace] == ["CLUSTER_FAILURE", "FALLBACK_LOCAL"]

    retry_profiler = RuntimeProfiler()
    runtime.handle_cluster_failure(
        request,
        runtime.plan(request),
        ClusterFailurePolicy.RETRY,
        retry_profiler,
    )
    assert [item["event"] for item in retry_profiler.trace] == [
        "CLUSTER_FAILURE",
        "CLUSTER_RETRY",
    ]


def test_cluster_execution_trace_includes_offload_execute_and_reduce():
    runtime = _orchestrator()
    result = runtime.execute(ExecutionRequest(
        "cluster-trace",
        {"workload": {"parallelizable": True, "estimated_operations": 100_000}},
    ))
    assert [item["event"] for item in result.trace] == [
        "CLUSTER_PLANNED",
        "CLUSTER_EXECUTE",
        "REDUCE",
    ]
    assert result.profile["cluster_offloads"] == 1


def test_observation_on_and_off_preserve_semantic_result_and_digest():
    runtime = _orchestrator()
    request = ExecutionRequest("observation-parity", {"id": 1})
    observed = runtime.execute(request, profiler=RuntimeProfiler(enabled=True))
    unobserved = runtime.execute(request, profiler=RuntimeProfiler(enabled=False))

    assert observed.value == unobserved.value
    assert observed.semantic_digest == unobserved.semantic_digest
    assert observed.trace[0]["event"] == "LOCAL"
    assert unobserved.trace == ()
    assert unobserved.profile["observation_enabled"] is False


def test_pressure_trace_records_safe_boundary_and_escalation():
    runtime = _orchestrator()
    request = ExecutionRequest(
        "pressure",
        {"operations": ["a"], "workload": {"parallelizable": True}},
    )
    profiler = RuntimeProfiler()
    decision = runtime.escalate(
        runtime.plan(request),
        RuntimePressure(live_tensors=10, memory_usage=100),
        safe_boundary=True,
        profiler=profiler,
    )
    assert decision.placement == "CLUSTER_ESCALATED"
    assert [item["event"] for item in profiler.trace] == [
        "PRESSURE",
        "SAFE_BOUNDARY",
        "CLUSTER_ESCALATED",
    ]


def test_transformer_relation_matrix_baseline_contract_and_diff_artifacts():
    runtime = _orchestrator()
    request = ExecutionRequest("relation-matrix", {"operations": ["matmul", "softmax"]})
    tensor_runtime = TensorRuntime()
    left = tensor_runtime.create([1.0], "f64")
    right = tensor_runtime.create([2.0], "f64")
    tensor_runtime.add(left, right)
    tensor_runtime.release(left)
    tensor_runtime.release(right)
    tensor_metrics = tensor_runtime.lifetime_metrics()
    profiler = RuntimeProfiler()
    profiler.observe_tensor_metrics(tensor_metrics)
    result = runtime.execute(request, profiler=profiler)
    pressure = RuntimePressure.from_tensor_metrics(
        tensor_metrics,
        execution_latency_ms=10.0,
    )
    baseline = capture_relation_matrix_baseline(result, pressure)
    comparison = compare_runtime_baseline(baseline, baseline)
    artifacts = runtime.artifacts(
        request,
        runtime.plan(request),
        pressure,
        profiler,
        result,
        baseline,
        comparison,
    )

    assert comparison["status"] == "PASS"
    assert comparison["checks"] == {
        "fixture_match": True,
        "semantic_digest_match": True,
        "execution_time_target": True,
        "peak_live_tensors_target": True,
        "release_balance_target": True,
    }
    assert artifacts["performance_baseline.json"]["fixture_id"] == "Transformer_Test.RelationMatrix"
    assert artifacts["baseline_comparison.json"]["status"] == "PASS"
    assert artifacts["determinism_manifest.json"]["observation_affects_result"] is False

    regression = RuntimeBaseline(
        baseline.fixture_id,
        "sha256:regression",
        {**baseline.profile, "peak_live_tensors": 4, "tensor_releases": 1},
        baseline.pressure,
        baseline.targets,
    )
    rejected = compare_runtime_baseline(baseline, regression)
    assert rejected["status"] == "FAIL"
    assert rejected["checks"]["semantic_digest_match"] is False
    assert rejected["checks"]["peak_live_tensors_target"] is False
    assert rejected["checks"]["release_balance_target"] is False
