"""Internal helper: resolve a RuntimeEngineRegistry from a registry or backend name."""

from __future__ import annotations

from frontend.runtime_integration import (
    RuntimeEngineRegistry,
    runtime_real_registry,
    hybrid_runtime_registry,
)

SUPPORTED_BACKENDS = {"RuntimeReal", "HybridRuntime"}


def resolve_registry(
    registry: RuntimeEngineRegistry | str | None,
) -> RuntimeEngineRegistry:
    if registry is None or registry == "RuntimeReal":
        return runtime_real_registry()
    if registry == "HybridRuntime":
        return hybrid_runtime_registry()
    if isinstance(registry, RuntimeEngineRegistry):
        return registry
    raise ValueError(f"Unknown backend: {registry!r}")
