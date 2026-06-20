"""runtime SDK package - typed access to RuntimeReal / HybridRuntime engines."""

from frontend.runtime_integration import (
    CallFrame,
    CallFrameStatus,
    CallStack,
    EXECUTION_ARCHITECTURE_SCHEMA,
    ExecutionCoordinator,
    ExecutionDiagnostics,
    ExecutionFailure,
    ExecutionFailureType,
    ExecutionRequest,
    ExecutionResult,
    StackOverflow,
)

__all__ = [
    "CallFrame",
    "CallFrameStatus",
    "CallStack",
    "EXECUTION_ARCHITECTURE_SCHEMA",
    "ExecutionCoordinator",
    "ExecutionDiagnostics",
    "ExecutionFailure",
    "ExecutionFailureType",
    "ExecutionRequest",
    "ExecutionResult",
    "StackOverflow",
]
