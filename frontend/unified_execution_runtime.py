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


class ExecutionBackend(Protocol):
    capability: RuntimeCapability

    def execute(self, request: ExecutionRequest) -> Any: ...


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


class UnifiedExecutionOrchestrator:
    """Capability-driven local-first planner with explicit escalation events."""

    def __init__(self, backends: Iterable[ExecutionBackend], *, policy_version: str = "UERA-0.1") -> None:
        self.backends = {backend.capability.backend_id: backend for backend in backends}
        self.policy_version = policy_version
        if not self.backends:
            raise ValueError("UER-CAP-001: at least one execution backend is required")

    def capabilities(self) -> list[RuntimeCapability]:
        return [self.backends[key].capability for key in sorted(self.backends)]

    def plan(self, request: ExecutionRequest, *, preferred_backend: str | None = None) -> ExecutionDecision:
        workload = request.workload
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

    def canonical_partitions(self, request: ExecutionRequest, operation_ids: Iterable[str], workers: Iterable[str]) -> list[ExecutionPartition]:
        workers = sorted(workers)
        if not workers:
            raise ValueError("UER-OFF-001: no cluster workers available")
        plan_bytes = _canonical_json(request.execution_plan)
        result = []
        for index, operation_id in enumerate(operation_ids):
            seed = plan_bytes + b":" + operation_id.encode() + b":" + str(index).encode() + b":" + self.policy_version.encode()
            result.append(ExecutionPartition(index, operation_id, hashlib.sha256(seed).hexdigest(), workers[index % len(workers)]))
        return result

    def execute(self, request: ExecutionRequest, *, preferred_backend: str | None = None) -> ExecutionResult:
        decision = self.plan(request, preferred_backend=preferred_backend)
        started = time.perf_counter()
        value = self.backends[decision.backend_id].execute(request)
        event = {"step": 1, "event": decision.placement, "backend": decision.backend_id, "reason": decision.reason, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}
        return ExecutionResult(request.request_id, value, decision.backend_id, (event,))

    def artifacts(self, request: ExecutionRequest, decision: ExecutionDecision, pressure: RuntimePressure | None = None) -> dict[str, Any]:
        return {
            "execution_plan.json": dict(request.execution_plan),
            "runtime_capabilities.json": [asdict(item) for item in self.capabilities()],
            "workload_estimate.json": asdict(request.workload),
            "runtime_pressure.json": asdict(pressure or RuntimePressure()),
            "cluster_plan.json": {"used": decision.placement.startswith("CLUSTER"), "placement": decision.placement, "backend": decision.backend_id},
            "determinism_manifest.json": {"policy_version": decision.policy_version, "canonical_json": True},
        }
