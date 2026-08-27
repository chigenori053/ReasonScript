import json
from dataclasses import dataclass

from frontend.unified_execution_runtime import ExecutionRequest, RuntimeCapability, UnifiedExecutionOrchestrator


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
