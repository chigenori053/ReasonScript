from dataclasses import dataclass

from frontend.unified_execution_runtime import (
    ExecutionRequest, RuntimeCapability, RuntimePressure, UnifiedExecutionOrchestrator,
    WorkloadEstimate,
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
