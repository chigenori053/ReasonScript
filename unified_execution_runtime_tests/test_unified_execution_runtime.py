from dataclasses import dataclass

from frontend.unified_execution_runtime import (
    ClusterFailurePolicy, ClusterRuntimeAdapter, ExecutionRequest, RuntimeCapability, RuntimePressure, RuntimeProfiler, UnifiedExecutionOrchestrator,
    WorkloadEstimate, WorkloadEstimator,
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
    decision = runtime.plan(ExecutionRequest("r", {"id": 1}))
    pressure = RuntimePressure(live_tensors=10)
    assert runtime.escalate(decision, pressure, safe_boundary=False).placement == "LOCAL"
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
