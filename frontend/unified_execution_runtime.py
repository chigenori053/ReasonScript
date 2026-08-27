"""Unified Execution Runtime v0.1 planning and deterministic orchestration.

This module deliberately keeps execution backends physically separate.  It owns
only capability discovery, placement policy, pressure accounting, canonical
partitioning and the durable execution artifacts consumed by diagnostics.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol

RELATION_MATRIX_FIXTURE_ID = "Transformer_Test.RelationMatrix"
RELATION_MATRIX_EXECUTION_TARGET_MS = 1_500.0


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

    @classmethod
    def from_tensor_metrics(
        cls, metrics: Mapping[str, Any], *, execution_latency_ms: float = 0.0
    ) -> RuntimePressure:
        latency_seconds = execution_latency_ms / 1_000
        allocations = int(metrics.get("tensor_allocations", 0))
        return cls(
            live_tensors=int(metrics.get("live_tensors", 0)),
            memory_usage=int(metrics.get("live_memory_bytes", 0)),
            autograd_nodes=int(metrics.get("autograd_nodes", 0)),
            execution_latency_ms=execution_latency_ms,
            allocation_rate=allocations / latency_seconds if latency_seconds else 0.0,
        )

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

    enabled: bool = True
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
        if not self.enabled:
            return entry
        self.trace.append(entry)
        if event in {"CLUSTER_PLANNED", "CLUSTER_ESCALATED"}:
            self.cluster_offloads += 1
        return entry

    def observe_pressure(self, pressure: RuntimePressure) -> None:
        if not self.enabled:
            return
        self.peak_live_tensors = max(self.peak_live_tensors, pressure.live_tensors)
        self.autograd_nodes = max(self.autograd_nodes, pressure.autograd_nodes)

    def observe_tensor_metrics(self, metrics: Mapping[str, Any]) -> None:
        if not self.enabled:
            return
        self.tensor_allocations = max(
            self.tensor_allocations, int(metrics.get("tensor_allocations", 0))
        )
        self.tensor_releases = max(
            self.tensor_releases, int(metrics.get("tensor_releases", 0))
        )
        self.peak_live_tensors = max(
            self.peak_live_tensors, int(metrics.get("peak_live_tensors", 0))
        )
        self.autograd_nodes = max(
            self.autograd_nodes, int(metrics.get("autograd_nodes", 0))
        )

    def snapshot(self) -> dict[str, Any]:
        return {"observation_enabled": self.enabled, "execution_time_ns": time.perf_counter_ns() - self.started_ns if self.enabled else 0, "function_calls": self.function_calls, "tensor_allocations": self.tensor_allocations, "tensor_releases": self.tensor_releases, "peak_live_tensors": self.peak_live_tensors, "autograd_nodes": self.autograd_nodes, "branch_evaluations": self.branch_evaluations, "cluster_offloads": self.cluster_offloads, "worker_tasks": self.worker_tasks, "transfer_bytes": self.transfer_bytes, "merge_time_ns": self.merge_time_ns}


@dataclass(frozen=True)
class ExecutionRequest:
    request_id: str
    execution_plan: Mapping[str, Any]
    workload: WorkloadEstimate = field(default_factory=WorkloadEstimate)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_reason_ir(
        cls,
        request_id: str,
        reason_ir: Mapping[str, Any],
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> ExecutionRequest:
        from frontend.language_surface.integration import execution_plan_for

        return cls(
            request_id,
            execution_plan_for(dict(reason_ir)),
            metadata=dict(metadata or {}),
        )


@dataclass(frozen=True)
class ExecutionResult:
    request_id: str
    value: Any
    backend_id: str
    trace: tuple[Mapping[str, Any], ...] = ()
    profile: Mapping[str, Any] = field(default_factory=dict)
    semantic_digest: str = ""


@dataclass(frozen=True)
class RuntimeBaseline:
    fixture_id: str
    semantic_digest: str
    profile: Mapping[str, Any]
    pressure: Mapping[str, Any]
    targets: Mapping[str, Any]
    schema_version: str = "reasonscript-runtime-baseline/0.1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def capture_runtime_baseline(
    fixture_id: str,
    result: ExecutionResult,
    pressure: RuntimePressure,
    *,
    max_execution_time_ms: float = 1_500.0,
    max_peak_live_tensors: int | None = None,
) -> RuntimeBaseline:
    """Capture the fixed Transformer/Relation Matrix observation contract."""
    profile = dict(result.profile)
    peak_limit = (
        int(max_peak_live_tensors)
        if max_peak_live_tensors is not None
        else int(profile.get("peak_live_tensors", 0))
    )
    return RuntimeBaseline(
        fixture_id,
        result.semantic_digest or _semantic_digest(result.value),
        profile,
        {**asdict(pressure), "level": pressure.level().value},
        {
            "max_execution_time_ms": float(max_execution_time_ms),
            "max_peak_live_tensors": peak_limit,
            "max_unreleased_tensors": max(
                0,
                int(profile.get("tensor_allocations", 0))
                - int(profile.get("tensor_releases", 0)),
            ),
            "require_semantic_digest_match": True,
        },
    )


def capture_relation_matrix_baseline(
    result: ExecutionResult, pressure: RuntimePressure
) -> RuntimeBaseline:
    return capture_runtime_baseline(
        RELATION_MATRIX_FIXTURE_ID,
        result,
        pressure,
        max_execution_time_ms=RELATION_MATRIX_EXECUTION_TARGET_MS,
        max_peak_live_tensors=int(result.profile.get("peak_live_tensors", 0)),
    )


def compare_runtime_baseline(
    reference: RuntimeBaseline, candidate: RuntimeBaseline
) -> dict[str, Any]:
    """Return deterministic pass/fail decisions while excluding raw timing deltas."""
    execution_time_ms = int(candidate.profile.get("execution_time_ns", 0)) / 1_000_000
    unreleased = max(
        0,
        int(candidate.profile.get("tensor_allocations", 0))
        - int(candidate.profile.get("tensor_releases", 0)),
    )
    checks = {
        "fixture_match": candidate.fixture_id == reference.fixture_id,
        "semantic_digest_match": candidate.semantic_digest == reference.semantic_digest,
        "execution_time_target": execution_time_ms
        <= float(reference.targets["max_execution_time_ms"]),
        "peak_live_tensors_target": int(
            candidate.profile.get("peak_live_tensors", 0)
        )
        <= int(reference.targets["max_peak_live_tensors"]),
        "release_balance_target": unreleased
        <= int(reference.targets["max_unreleased_tensors"]),
    }
    return {
        "schema_version": "reasonscript-runtime-baseline-comparison/0.1",
        "fixture_id": reference.fixture_id,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "observed": {
            "execution_time_ms": execution_time_ms,
            "peak_live_tensors": int(
                candidate.profile.get("peak_live_tensors", 0)
            ),
            "unreleased_tensors": unreleased,
        },
        "targets": dict(reference.targets),
    }


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


def _identity_value(request: ExecutionRequest) -> Any:
    """Read the backend-neutral identity probe from an execution plan."""
    operation = request.execution_plan.get("operation")
    if operation != "identity":
        raise ValueError(f"UER-REQ-001: unsupported operation {operation!r}")
    arguments = request.execution_plan.get("arguments")
    if not isinstance(arguments, (list, tuple)) or len(arguments) != 1:
        raise ValueError("UER-REQ-002: identity requires exactly one argument")
    return arguments[0]


def _tensor_runner(request: ExecutionRequest) -> Any:
    """Execute the common probe through the existing TensorRuntime backend."""
    from frontend.tensor.runtime import TensorRuntime

    runtime = TensorRuntime()
    tensor = runtime.call("tensor.create", _identity_value(request))
    return runtime.to_array(tensor)


def _rust_runner(crate: str, binary: str) -> Callable[[ExecutionRequest], Any]:
    """Connect a RuntimeAdapter to a Rust runtime's JSON execution boundary."""
    repository = Path(__file__).resolve().parents[1]
    manifest = repository / crate / "Cargo.toml"

    def execute(request: ExecutionRequest) -> Any:
        # Cargo's incremental check prevents a checked-in or cached target from
        # silently running an adapter older than the source contract.
        command = [
            "cargo", "run", "--quiet", "--manifest-path", str(manifest),
            "--bin", binary, "--", "uera-execute",
        ]
        payload = {
            "schema_version": "reasonscript-execution-request/0.1",
            "request_id": request.request_id,
            "execution_plan": dict(request.execution_plan),
            "metadata": dict(request.metadata),
        }
        try:
            completed = subprocess.run(
                command,
                input=json.dumps(payload, sort_keys=True, separators=(",", ":")),
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as error:
            raise RuntimeError(
                f"UER-BKD-002: failed to start backend {crate}: {error}"
            ) from error
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(
                f"UER-BKD-003: backend {crate} returned invalid JSON: {detail}"
            ) from error
        if completed.returncode != 0 or response.get("ok") is not True:
            raise RuntimeError(
                f"UER-BKD-004: backend {crate} rejected request: {response.get('diagnostics', response)}"
            )
        if response.get("request_id") != request.request_id:
            raise RuntimeError(f"UER-BKD-005: backend {crate} returned a mismatched request ID")
        return response.get("value")

    return execute


@dataclass(frozen=True)
class ClusterRuntimeAdapter:
    """Adapter boundary for the existing ClusterRuntime worker executor.

    The adapter owns scheduling metadata only.  Computation stays in the
    worker's selected execution backend.
    """

    workers: tuple[str, ...]
    worker_execute: Callable[[ExecutionPartition, ExecutionRequest], Any]
    available_workers: tuple[str, ...] | None = None
    policy_version: str = "UERA-0.1"
    reduction: str = "canonical_list"
    planner: Callable[..., Mapping[str, Any]] | None = None
    last_plan: dict[str, Any] = field(default_factory=dict, compare=False)
    capability: RuntimeCapability = field(default_factory=lambda: RuntimeCapability(
        "ClusterRuntime",
        "rust",
        ("orchestration",),
        ("Int", "Float", "Bool", "Complex"),
        tensor_support=True,
        autograd_support=True,
        complex_support=True,
        reason_unit_support=True,
        parallel_execution=True,
    ))

    def execute(self, request: ExecutionRequest) -> Any:
        operations = _operation_ids(request.execution_plan)
        partitions = self.partitions(request, operations)
        completed = [(partition, self.worker_execute(partition, request)) for partition in partitions]
        reduced = self.reduce(completed)
        if self.reduction == "single_result" and len(reduced) == 1:
            return reduced[0]
        return reduced

    def partitions(self, request: ExecutionRequest, operation_ids: Iterable[str]) -> list[ExecutionPartition]:
        operation_ids = tuple(operation_ids)
        available = (
            self.workers if self.available_workers is None else self.available_workers
        )
        planner = self.planner or _cluster_plan_runner
        plan = dict(planner(
            request,
            operation_ids,
            self.workers,
            available,
            self.policy_version,
        ))
        self.last_plan.clear()
        self.last_plan.update(plan)
        return [
            ExecutionPartition(
                int(item["partition_index"]),
                str(item["operation_id"]),
                str(item["partition_id"]),
                str(item["assigned_worker"]),
                str(item["preferred_worker"]),
                bool(item["fallback_used"]),
            )
            for item in plan["partitions"]
        ]

    @staticmethod
    def reduce(completed: Iterable[tuple[ExecutionPartition, Any]]) -> list[Any]:
        """Never use completion order for a distributed reduction."""
        return [value for _, value in sorted(completed, key=lambda item: item[0].partition_index)]


@dataclass(frozen=True)
class ClusterWorkerExecutor:
    """Dispatch a cluster partition through an existing local runtime adapter."""

    backends: tuple[RuntimeAdapter, ...]

    def __call__(self, partition: ExecutionPartition, request: ExecutionRequest) -> Any:
        orchestrator = UnifiedExecutionOrchestrator(self.backends)
        backend_id = orchestrator.resolve_backend(request, parallel=False)
        return orchestrator.backends[backend_id].execute(request)


def _local_runtime_adapters() -> tuple[RuntimeAdapter, ...]:
    return (
        RuntimeAdapter(RuntimeCapability("RuntimeReal", "rust", ("identity", "scalar", "reasoning"), ("Int", "Float", "Bool")), _rust_runner("RuntimeReal", "uera_adapter")),
        RuntimeAdapter(RuntimeCapability("TensorRuntime", "python", ("identity", "tensor", "autograd"), ("Int", "Float"), tensor_support=True, autograd_support=True, memory_limit=256 * 1024 * 1024, tensor_limit=1_000), _tensor_runner),
        RuntimeAdapter(RuntimeCapability("RuntimeComplex", "rust", ("identity", "complex"), ("Int", "Float", "Complex"), complex_support=True), _rust_runner("RuntimeComplex", "uera_adapter")),
        RuntimeAdapter(RuntimeCapability("ReasonUnitRuntime", "rust", ("identity", "reason_unit"), reason_unit_support=True), _rust_runner("NativeReasonUnitRuntime", "reasonunit-runtime-native")),
    )


def default_runtime_adapters() -> tuple[ExecutionBackend, ...]:
    """Return the v0.1 catalog with executable adapters for every local Runtime."""
    local = _local_runtime_adapters()
    cluster = ClusterRuntimeAdapter(
        ("worker-0", "worker-1"),
        ClusterWorkerExecutor(local),
        reduction="single_result",
    )
    return (*local, cluster)


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
    preferred_worker: str = ""
    fallback_used: bool = False


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _semantic_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _canonical_partitions(
    request: ExecutionRequest,
    operation_ids: Iterable[str],
    workers: Iterable[str],
    policy_version: str,
    available_workers: Iterable[str] | None = None,
) -> list[ExecutionPartition]:
    workers = sorted(set(workers))
    if not workers:
        raise ValueError("CRR-UER-001: no cluster workers configured")
    available = set(available_workers if available_workers is not None else workers)
    if not available:
        raise ValueError("CRR-UER-002: no cluster workers available")
    if not available <= set(workers):
        raise ValueError("CRR-UER-003: available worker is not configured")
    result = []
    for index, operation_id in enumerate(operation_ids):
        preferred_index = index % len(workers)
        preferred = workers[preferred_index]
        assigned = next(
            workers[(preferred_index + offset) % len(workers)]
            for offset in range(len(workers))
            if workers[(preferred_index + offset) % len(workers)] in available
        )
        partition_payload = {
            "execution_plan": request.execution_plan,
            "operation_id": operation_id,
            "partition_index": index,
            "policy_version": policy_version,
        }
        partition_id = "sha256:" + hashlib.sha256(
            _canonical_json(partition_payload)
        ).hexdigest()
        result.append(ExecutionPartition(
            index,
            operation_id,
            partition_id,
            assigned,
            preferred,
            assigned != preferred,
        ))
    return result


def _operation_ids(execution_plan: Mapping[str, Any]) -> tuple[str, ...]:
    operations = execution_plan.get(
        "operations", execution_plan.get("selected_steps", execution_plan.get("steps", ()))
    )
    result = []
    for index, item in enumerate(operations):
        if isinstance(item, Mapping):
            operation_id = item.get("operation_id", item.get("transition_id", item.get("id")))
            result.append(str(operation_id if operation_id is not None else index))
        else:
            result.append(str(item))
    if not result and execution_plan.get("operation") is not None:
        result.append(str(execution_plan["operation"]))
    if not result:
        result.append("execution-plan")
    return tuple(result)


def _cluster_plan_runner(
    request: ExecutionRequest,
    operation_ids: Iterable[str],
    workers: Iterable[str],
    available_workers: Iterable[str],
    policy_version: str,
) -> Mapping[str, Any]:
    """Plan partitions through the existing Rust ClusterRuntime boundary."""
    repository = Path(__file__).resolve().parents[1]
    command = [
        "cargo", "run", "--quiet", "--manifest-path",
        str(repository / "ClusterRuntime" / "Cargo.toml"),
        "--bin", "reason-cluster", "--", "uera-plan",
    ]
    payload = {
        "execution_plan": dict(request.execution_plan),
        "operation_ids": list(operation_ids),
        "workers": list(workers),
        "available_workers": list(available_workers),
        "policy_version": policy_version,
    }
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(payload, sort_keys=True, separators=(",", ":")),
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise RuntimeError(
            f"UER-OFF-004: failed to start ClusterRuntime: {error}"
        ) from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"UER-OFF-004: ClusterRuntime planning failed: {detail}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "UER-OFF-005: ClusterRuntime returned an invalid UERA plan"
        ) from error


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

    def resolve_backend(
        self,
        request: ExecutionRequest,
        *,
        preferred_backend: str | None = None,
        parallel: bool = False,
    ) -> str:
        requirements = request.execution_plan.get("requirements", {})
        if preferred_backend is not None:
            if preferred_backend not in self.backends:
                raise ValueError(f"UER-CAP-002: unknown backend {preferred_backend}")
            capability = self.backends[preferred_backend].capability
            if capability.parallel_execution != parallel or not _supports_requirements(
                capability, requirements
            ):
                raise ValueError(
                    f"UER-CAP-003: backend {preferred_backend} does not satisfy execution requirements"
                )
            return preferred_backend
        candidates = [
            key
            for key, backend in self.backends.items()
            if backend.capability.parallel_execution == parallel
            and _supports_requirements(backend.capability, requirements)
        ]
        if not candidates:
            kind = "parallel" if parallel else "local"
            raise ValueError(f"UER-CAP-004: no compatible {kind} backend")
        priority = {
            "RuntimeReal": 0,
            "TensorRuntime": 1,
            "RuntimeComplex": 2,
            "ReasonUnitRuntime": 3,
            "ClusterRuntime": 4,
        }
        return min(candidates, key=lambda key: (priority.get(key, 100), key))

    def plan(self, request: ExecutionRequest, *, preferred_backend: str | None = None) -> ExecutionDecision:
        workload = self.estimate_workload(request)
        local = self.resolve_backend(
            request, preferred_backend=preferred_backend, parallel=False
        )
        cluster = next((key for key in sorted(self.backends) if self.backends[key].capability.parallel_execution), None)
        high = workload.parallelizable and (
            workload.estimated_operations >= 100_000
            or workload.estimated_memory >= 64 * 1024 * 1024
            or workload.estimated_peak_live_tensors >= 1_000
        )
        if high and cluster:
            return ExecutionDecision("CLUSTER_PLANNED", cluster, "parallel workload exceeds planned-offload threshold", workload, self.policy_version)
        mode = "LOCAL_MONITORED" if workload.parallelizable else "LOCAL"
        return ExecutionDecision(mode, local, "local-first policy", workload, self.policy_version)

    def escalate(self, decision: ExecutionDecision, pressure: RuntimePressure, *, safe_boundary: bool, profiler: RuntimeProfiler | None = None) -> ExecutionDecision:
        if profiler is not None:
            profiler.observe_pressure(pressure)
            profiler.record(
                "PRESSURE",
                backend=decision.backend_id,
                level=pressure.level(self.backends[decision.backend_id].capability).value,
                live_tensors=pressure.live_tensors,
                memory_usage=pressure.memory_usage,
                autograd_nodes=pressure.autograd_nodes,
            )
            profiler.record("SAFE_BOUNDARY", available=safe_boundary)
        capability = self.backends[decision.backend_id].capability
        if pressure.level(capability) in {PressureLevel.HIGH, PressureLevel.CRITICAL} and safe_boundary:
            cluster = next((key for key in sorted(self.backends) if self.backends[key].capability.parallel_execution), None)
            if cluster:
                escalated = ExecutionDecision("CLUSTER_ESCALATED", cluster, "runtime pressure at safe boundary", decision.workload, self.policy_version)
                if profiler is not None:
                    profiler.record("CLUSTER_ESCALATED", backend=cluster, reason=escalated.reason)
                return escalated
        if profiler is not None:
            profiler.record("LOCAL_CONTINUE", backend=decision.backend_id)
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
        if profiler.enabled:
            profiler.function_calls += 1
        capability = self.backends[decision.backend_id].capability
        if capability.parallel_execution:
            profiler.record("CLUSTER_EXECUTE", backend=decision.backend_id)
        value = self.backends[decision.backend_id].execute(request)
        if capability.parallel_execution:
            cluster_plan = getattr(
                self.backends[decision.backend_id], "last_plan", {}
            )
            if cluster_plan:
                profiler.worker_tasks += len(cluster_plan.get("partitions", ()))
            elif isinstance(value, (list, tuple)):
                profiler.worker_tasks += len(value)
            profiler.record("REDUCE", ordering="canonical")
        digest = _semantic_digest(value)
        return ExecutionResult(
            request.request_id,
            value,
            decision.backend_id,
            tuple(dict(item) for item in profiler.trace),
            profiler.snapshot(),
            digest,
        )

    def artifacts(self, request: ExecutionRequest, decision: ExecutionDecision, pressure: RuntimePressure | None = None, profiler: RuntimeProfiler | None = None, result: ExecutionResult | None = None, baseline: RuntimeBaseline | None = None, baseline_comparison: Mapping[str, Any] | None = None) -> dict[str, Any]:
        profiler = profiler or RuntimeProfiler()
        pressure = pressure or RuntimePressure()
        profiler.observe_pressure(pressure)
        cluster_backend = self.backends.get(decision.backend_id)
        cluster_plan = dict(getattr(cluster_backend, "last_plan", {}))
        if cluster_plan.get("source_plan_hash") != (
            "sha256:" + hashlib.sha256(_canonical_json(request.execution_plan)).hexdigest()
        ):
            cluster_plan = {}
        cluster_plan.update({
            "used": decision.placement.startswith("CLUSTER"),
            "placement": decision.placement,
            "backend": decision.backend_id,
        })
        return {
            "execution_plan.json": {
                **dict(request.execution_plan),
                "placement_decision": asdict(decision),
            },
            "runtime_capabilities.json": [asdict(item) for item in self.capabilities()],
            "workload_estimate.json": asdict(self.estimate_workload(request)),
            "runtime_pressure.json": {**asdict(pressure), "level": pressure.level(self.backends[decision.backend_id].capability).value},
            "runtime_profile.json": profiler.snapshot(),
            "execution_trace.json": list(profiler.trace),
            "cluster_plan.json": cluster_plan,
            "determinism_manifest.json": {"policy_version": decision.policy_version, "canonical_json": True, "observation_affects_result": False, "semantic_digest": result.semantic_digest if result is not None else None},
            "execution_result.json": {"request_id": result.request_id, "backend": result.backend_id, "value": result.value, "semantic_digest": result.semantic_digest} if result is not None else None,
            "performance_baseline.json": baseline.to_dict() if baseline is not None else None,
            "baseline_comparison.json": dict(baseline_comparison) if baseline_comparison is not None else None,
        }


def _supports_requirements(
    capability: RuntimeCapability, requirements: Mapping[str, Any]
) -> bool:
    for field_name in (
        "tensor_support",
        "autograd_support",
        "complex_support",
        "reason_unit_support",
    ):
        if bool(requirements.get(field_name, False)) and not getattr(
            capability, field_name
        ):
            return False
    numeric_types = {str(item) for item in requirements.get("numeric_types", ())}
    return numeric_types <= set(capability.numeric_types)
