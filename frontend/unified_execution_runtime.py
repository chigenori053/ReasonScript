"""Unified Execution Runtime v0.1 planning and deterministic orchestration.

This module deliberately keeps execution backends physically separate.  It owns
only capability discovery, placement policy, pressure accounting, canonical
partitioning and the durable execution artifacts consumed by diagnostics.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Callable, Iterable, Mapping, Protocol


class PressureLevel(StrEnum):
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ClusterFailurePolicy(StrEnum):
    RETRY = "retry"
    FALLBACK_LOCAL = "fallback_local"
    FALLBACK_SINGLE_NODE = "fallback_single_node"
    ABORT = "abort"


@dataclass(frozen=True)
class RuntimeCapability:
    backend_id: str
    execution_engine: str
    supported_operations: tuple[str, ...] = ()
    numeric_types: tuple[str, ...] = ("Int", "Float")
    tensor_support: bool = False
    autograd_support: bool = False
    complex_support: bool = False
    reason_unit_support: bool = False
    parallel_execution: bool = False
    deterministic: bool = True
    memory_limit: int | None = None
    tensor_limit: int | None = None


@dataclass(frozen=True)
class WorkloadEstimate:
    estimated_operations: int = 0
    estimated_memory: int = 0
    estimated_peak_live_tensors: int = 0
    estimated_autograd_nodes: int = 0
    parallelizable: bool = False
    dependency_depth: int = 0
    transfer_cost: int = 0


class WorkloadEstimator:
    """Derive a stable placement estimate from ExecutionPlan metadata."""

    @staticmethod
    def from_plan(plan: Mapping[str, Any]) -> WorkloadEstimate:
        metadata = plan.get("workload", plan.get("metadata", {}))
        operations = plan.get("operations", plan.get("steps", ()))
        return WorkloadEstimate(
            estimated_operations=int(metadata.get("estimated_operations", len(operations))),
            estimated_memory=int(metadata.get("estimated_memory", 0)),
            estimated_peak_live_tensors=int(metadata.get("estimated_peak_live_tensors", 0)),
            estimated_autograd_nodes=int(metadata.get("estimated_autograd_nodes", 0)),
            parallelizable=bool(metadata.get("parallelizable", False)),
            dependency_depth=int(metadata.get("dependency_depth", 0)),
            transfer_cost=int(metadata.get("transfer_cost", 0)),
        )


@dataclass(frozen=True)
class RuntimePressure:
    live_tensors: int = 0
    memory_usage: int = 0
    autograd_nodes: int = 0
    execution_latency_ms: float = 0.0
    allocation_rate: float = 0.0

    def level(self, capability: RuntimeCapability | None = None) -> PressureLevel:
        tensor_limit = capability.tensor_limit if capability else None
        memory_limit = capability.memory_limit if capability else None
        tensor_ratio = self.live_tensors / tensor_limit if tensor_limit else 0.0
        memory_ratio = self.memory_usage / memory_limit if memory_limit else 0.0
        ratio = max(tensor_ratio, memory_ratio)
        if ratio >= 1.0:
            return PressureLevel.CRITICAL
        if ratio >= 0.8:
            return PressureLevel.HIGH
        if ratio >= 0.6:
            return PressureLevel.ELEVATED
        return PressureLevel.NORMAL


@dataclass
class RuntimeProfiler:
    """Deterministic metrics and trace recorder for one execution request."""

    started_ns: int = field(default_factory=time.perf_counter_ns)
    function_calls: int = 0
    tensor_allocations: int = 0
    tensor_releases: int = 0
    peak_live_tensors: int = 0
    autograd_nodes: int = 0
    branch_evaluations: int = 0
    cluster_offloads: int = 0
    worker_tasks: int = 0
    transfer_bytes: int = 0
    merge_time_ns: int = 0
    trace: list[dict[str, Any]] = field(default_factory=list)

    def record(self, event: str, **details: Any) -> dict[str, Any]:
        entry = {"step": len(self.trace) + 1, "event": event, **details}
        self.trace.append(entry)
        if event.startswith("CLUSTER"):
            self.cluster_offloads += 1
        return entry

    def observe_pressure(self, pressure: RuntimePressure) -> None:
        self.peak_live_tensors = max(self.peak_live_tensors, pressure.live_tensors)
        self.autograd_nodes = max(self.autograd_nodes, pressure.autograd_nodes)

    def snapshot(self) -> dict[str, Any]:
        return {"execution_time_ns": time.perf_counter_ns() - self.started_ns, "function_calls": self.function_calls, "tensor_allocations": self.tensor_allocations, "tensor_releases": self.tensor_releases, "peak_live_tensors": self.peak_live_tensors, "autograd_nodes": self.autograd_nodes, "branch_evaluations": self.branch_evaluations, "cluster_offloads": self.cluster_offloads, "worker_tasks": self.worker_tasks, "transfer_bytes": self.transfer_bytes, "merge_time_ns": self.merge_time_ns}


@dataclass(frozen=True)
class ExecutionRequest:
    request_id: str
    execution_plan: Mapping[str, Any]
    workload: WorkloadEstimate = field(default_factory=WorkloadEstimate)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionResult:
    request_id: str
    value: Any
    backend_id: str
    trace: tuple[Mapping[str, Any], ...] = ()
    profile: Mapping[str, Any] = field(default_factory=dict)


class ExecutionBackend(Protocol):
    capability: RuntimeCapability

    def execute(self, request: ExecutionRequest) -> Any: ...


@dataclass(frozen=True)
class RuntimeAdapter:
    """A backend-neutral adapter used by the UEO runtime registry.

    Backends retain their implementation language and process boundary; an
    adapter only exposes the common contract and an explicitly supplied call.
    """

    capability: RuntimeCapability
    runner: Callable[[ExecutionRequest], Any] | None = None

    def execute(self, request: ExecutionRequest) -> Any:
        if self.runner is None:
            raise RuntimeError(f"UER-BKD-001: backend {self.capability.backend_id} has no execution adapter")
        return self.runner(request)


@dataclass(frozen=True)
class ClusterRuntimeAdapter:
    """Adapter boundary for the existing ClusterRuntime worker executor.

    The adapter owns scheduling metadata only.  Computation stays in the
    worker's selected execution backend.
    """

    workers: tuple[str, ...]
    worker_execute: Callable[[ExecutionPartition, ExecutionRequest], Any]
    capability: RuntimeCapability = field(default_factory=lambda: RuntimeCapability("ClusterRuntime", "rust", ("orchestration",), parallel_execution=True))

    def execute(self, request: ExecutionRequest) -> Any:
        operations = request.execution_plan.get("operations", request.execution_plan.get("steps", ()))
        partitions = self.partitions(request, [str(item) for item in operations])
        completed = [(partition, self.worker_execute(partition, request)) for partition in partitions]
        return self.reduce(completed)

    def partitions(self, request: ExecutionRequest, operation_ids: Iterable[str]) -> list[ExecutionPartition]:
        return _canonical_partitions(request, operation_ids, self.workers, "UERA-0.1")

    @staticmethod
    def reduce(completed: Iterable[tuple[ExecutionPartition, Any]]) -> list[Any]:
        """Never use completion order for a distributed reduction."""
        return [value for _, value in sorted(completed, key=lambda item: item[0].partition_index)]


def default_runtime_adapters() -> tuple[RuntimeAdapter, ...]:
    """Return the v0.1 catalog without importing or coupling backend code."""
    return (
        RuntimeAdapter(RuntimeCapability("RuntimeReal", "rust", ("scalar", "reasoning"), ("Int", "Float", "Bool"))),
        RuntimeAdapter(RuntimeCapability("TensorRuntime", "python", ("tensor", "autograd"), ("Int", "Float"), tensor_support=True, autograd_support=True, memory_limit=256 * 1024 * 1024, tensor_limit=1_000)),
        RuntimeAdapter(RuntimeCapability("RuntimeComplex", "rust", ("complex",), ("Int", "Float", "Complex"), complex_support=True)),
        RuntimeAdapter(RuntimeCapability("ReasonUnitRuntime", "rust", ("reason_unit",), reason_unit_support=True)),
        RuntimeAdapter(RuntimeCapability("ClusterRuntime", "rust", ("orchestration",), parallel_execution=True)),
    )


def runtime_info() -> dict[str, Any]:
    """Stable, backend-transparent payload for ``reason runtime info``."""
    capabilities = [asdict(adapter.capability) for adapter in default_runtime_adapters()]
    return {
        "schema_version": "reasonscript-unified-execution-runtime/0.1",
        "orchestrator": {"enabled": True, "policy_version": "UERA-0.1"},
        "local_backends": [item["backend_id"] for item in capabilities if item["backend_id"] != "ClusterRuntime"],
        "cluster": {"enabled": True, "backend_id": "ClusterRuntime"},
        "backends": capabilities,
    }


@dataclass(frozen=True)
class ExecutionDecision:
    placement: str
    backend_id: str
    reason: str
    workload: WorkloadEstimate
    policy_version: str = "UERA-0.1"


@dataclass(frozen=True)
class ExecutionPartition:
    partition_index: int
    operation_id: str
    partition_id: str
    worker_id: str


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _canonical_partitions(request: ExecutionRequest, operation_ids: Iterable[str], workers: Iterable[str], policy_version: str) -> list[ExecutionPartition]:
    workers = sorted(workers)
    if not workers:
        raise ValueError("UER-OFF-001: no cluster workers available")
    plan_bytes = _canonical_json(request.execution_plan)
    result = []
    for index, operation_id in enumerate(operation_ids):
        seed = plan_bytes + b":" + operation_id.encode() + b":" + str(index).encode() + b":" + policy_version.encode()
        result.append(ExecutionPartition(index, operation_id, hashlib.sha256(seed).hexdigest(), workers[index % len(workers)]))
    return result


class UnifiedExecutionOrchestrator:
    """Capability-driven local-first planner with explicit escalation events."""

    def __init__(self, backends: Iterable[ExecutionBackend], *, policy_version: str = "UERA-0.1") -> None:
        self.backends = {backend.capability.backend_id: backend for backend in backends}
        self.policy_version = policy_version
        if not self.backends:
            raise ValueError("UER-CAP-001: at least one execution backend is required")

    def capabilities(self) -> list[RuntimeCapability]:
        return [self.backends[key].capability for key in sorted(self.backends)]

    def estimate_workload(self, request: ExecutionRequest) -> WorkloadEstimate:
        """Use an explicit request estimate when supplied, else read the plan."""
        if request.workload != WorkloadEstimate():
            return request.workload
        return WorkloadEstimator.from_plan(request.execution_plan)

    def plan(self, request: ExecutionRequest, *, preferred_backend: str | None = None) -> ExecutionDecision:
        workload = self.estimate_workload(request)
        local = preferred_backend or next(
            (key for key in sorted(self.backends) if not self.backends[key].capability.parallel_execution),
            next(iter(sorted(self.backends))),
        )
        if local not in self.backends:
            raise ValueError(f"UER-CAP-002: unknown backend {local}")
        cluster = next((key for key in sorted(self.backends) if self.backends[key].capability.parallel_execution), None)
        high = workload.parallelizable and (
            workload.estimated_operations >= 100_000
            or workload.estimated_memory >= 64 * 1024 * 1024
            or workload.estimated_peak_live_tensors >= 1_000
        )
        if high and cluster:
            return ExecutionDecision("CLUSTER_PLANNED", cluster, "workload estimate exceeds local-first threshold", workload, self.policy_version)
        mode = "LOCAL_MONITORED" if workload.parallelizable else "LOCAL"
        return ExecutionDecision(mode, local, "local-first policy", workload, self.policy_version)

    def escalate(self, decision: ExecutionDecision, pressure: RuntimePressure, *, safe_boundary: bool) -> ExecutionDecision:
        capability = self.backends[decision.backend_id].capability
        if pressure.level(capability) in {PressureLevel.HIGH, PressureLevel.CRITICAL} and safe_boundary:
            cluster = next((key for key in sorted(self.backends) if self.backends[key].capability.parallel_execution), None)
            if cluster:
                return ExecutionDecision("CLUSTER_ESCALATED", cluster, "runtime pressure at safe boundary", decision.workload, self.policy_version)
        return decision

    def handle_cluster_failure(self, request: ExecutionRequest, decision: ExecutionDecision, policy: ClusterFailurePolicy, profiler: RuntimeProfiler) -> ExecutionDecision:
        """Apply a declared policy; fallback is never implicit or untraced."""
        profiler.record("CLUSTER_FAILURE", backend=decision.backend_id, policy=policy.value)
        if policy == ClusterFailurePolicy.RETRY:
            profiler.record("CLUSTER_RETRY", backend=decision.backend_id)
            return decision
        if policy == ClusterFailurePolicy.ABORT:
            raise RuntimeError("UER-OFF-002: cluster execution failed and policy is abort")
        local = next((key for key in sorted(self.backends) if not self.backends[key].capability.parallel_execution), None)
        if local is None:
            raise RuntimeError("UER-OFF-003: no explicit local fallback backend")
        event = "FALLBACK_LOCAL" if policy == ClusterFailurePolicy.FALLBACK_LOCAL else "FALLBACK_SINGLE_NODE"
        profiler.record(event, backend=local)
        return ExecutionDecision(event, local, "declared cluster failure policy", self.estimate_workload(request), self.policy_version)

    def canonical_partitions(self, request: ExecutionRequest, operation_ids: Iterable[str], workers: Iterable[str]) -> list[ExecutionPartition]:
        return _canonical_partitions(request, operation_ids, workers, self.policy_version)

    def execute(self, request: ExecutionRequest, *, preferred_backend: str | None = None, profiler: RuntimeProfiler | None = None) -> ExecutionResult:
        profiler = profiler or RuntimeProfiler()
        decision = self.plan(request, preferred_backend=preferred_backend)
        profiler.record(decision.placement, backend=decision.backend_id, reason=decision.reason)
        started = time.perf_counter()
        value = self.backends[decision.backend_id].execute(request)
        event = {"step": 1, "event": decision.placement, "backend": decision.backend_id, "reason": decision.reason, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}
        return ExecutionResult(request.request_id, value, decision.backend_id, (event,), profiler.snapshot())

    def artifacts(self, request: ExecutionRequest, decision: ExecutionDecision, pressure: RuntimePressure | None = None, profiler: RuntimeProfiler | None = None, result: ExecutionResult | None = None) -> dict[str, Any]:
        profiler = profiler or RuntimeProfiler()
        pressure = pressure or RuntimePressure()
        profiler.observe_pressure(pressure)
        return {
            "execution_plan.json": dict(request.execution_plan),
            "runtime_capabilities.json": [asdict(item) for item in self.capabilities()],
            "workload_estimate.json": asdict(request.workload),
            "runtime_pressure.json": {**asdict(pressure), "level": pressure.level(self.backends[decision.backend_id].capability).value},
            "runtime_profile.json": profiler.snapshot(),
            "execution_trace.json": list(profiler.trace),
            "cluster_plan.json": {"used": decision.placement.startswith("CLUSTER"), "placement": decision.placement, "backend": decision.backend_id},
            "determinism_manifest.json": {"policy_version": decision.policy_version, "canonical_json": True},
            "execution_result.json": {"request_id": result.request_id, "backend": result.backend_id, "value": result.value} if result is not None else None,
        }
