"""Runtime Integration Phase 1/2 binding layer.

This module executes Runtime Namespace operations emitted in Reason IR metadata.
It is intentionally small and deterministic: concrete runtime engines implement
the executor interface, while the binding layer owns validation, conversion,
optional result mapping, and diagnostics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol


EXECUTION_ARCHITECTURE_SCHEMA = "reasonscript-execution-architecture/1.1"
RUNTIME_OPERATION_METHODS = {"search", "simulate", "predict", "plan"}
REASONING_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class RuntimeIntegrationErrorCode:
    UNKNOWN_RUNTIME_OPERATION = "RI-1 Unknown Runtime Operation"
    RUNTIME_BINDING_MISSING = "RI-2 Runtime Binding Missing"
    ARGUMENT_CONVERSION_FAILED = "RI-3 Runtime Argument Conversion Failed"
    RESULT_CONVERSION_FAILED = "RI-4 Runtime Result Conversion Failed"
    RUNTIME_EXECUTION_FAILED = "RI-5 Runtime Execution Failed"
    RUNTIME_ENGINE_MISSING = "RI2-2 Engine registry missing required engine"
    EXECUTION_PLAN_INCOMPATIBLE = "RI2-5 ExecutionPlan compatibility failed"
    TRACE_MISSING = "RI2-6 Runtime trace missing"
    REASONING_TYPE_CONVERSION_FAILED = "ReasoningTypeConversionFailed"


class ExecutionFailureType:
    VALIDATION_FAILED = "ValidationFailed"
    STACK_OVERFLOW = "StackOverflow"
    RUNTIME_FAILURE = "RuntimeFailure"


class CallFrameStatus:
    ACTIVE = "Active"
    RETURNING = "Returning"
    COMPLETED = "Completed"
    FAILED = "Failed"


@dataclass(frozen=True)
class RuntimeStruct:
    fields: dict[str, "RuntimeValue"]


@dataclass(frozen=True)
class RuntimeEnum:
    enum_name: str
    value_name: str


@dataclass(frozen=True)
class RuntimeValue:
    kind: str
    value: Any

    @staticmethod
    def bool(value: bool) -> "RuntimeValue":
        return RuntimeValue("Bool", value)

    @staticmethod
    def int(value: int) -> "RuntimeValue":
        return RuntimeValue("Int", value)

    @staticmethod
    def float(value: float) -> "RuntimeValue":
        return RuntimeValue("Float", value)

    @staticmethod
    def string(value: str) -> "RuntimeValue":
        return RuntimeValue("String", value)

    @staticmethod
    def struct(fields: dict[str, "RuntimeValue"]) -> "RuntimeValue":
        return RuntimeValue("Struct", RuntimeStruct(fields))

    @staticmethod
    def enum(enum_name: str, value_name: str) -> "RuntimeValue":
        return RuntimeValue("Enum", RuntimeEnum(enum_name, value_name))

    @staticmethod
    def array(values: list["RuntimeValue"]) -> "RuntimeValue":
        return RuntimeValue("Array", values)

    @staticmethod
    def optional(value: "RuntimeValue | None") -> "RuntimeValue":
        return RuntimeValue("Optional", value)

    @staticmethod
    def goal(name: str) -> "RuntimeValue":
        return RuntimeValue("GoalValue", {"name": name})

    @staticmethod
    def state(identifier: str) -> "RuntimeValue":
        return RuntimeValue("StateValue", {"id": identifier})

    @staticmethod
    def constraint(name: str) -> "RuntimeValue":
        return RuntimeValue("ConstraintValue", {"name": name})

    @staticmethod
    def reason_graph(value: dict[str, Any]) -> "RuntimeValue":
        return RuntimeValue("ReasonGraphValue", value)

    @staticmethod
    def execution_plan(value: dict[str, Any]) -> "RuntimeValue":
        return RuntimeValue("ExecutionPlanValue", value)


@dataclass(frozen=True)
class ExecutionDiagnostics:
    entries: tuple[str, ...] = ()

    def add(self, diagnostic: str) -> "ExecutionDiagnostics":
        return ExecutionDiagnostics(self.entries + (diagnostic,))

    def extend(self, diagnostics: tuple[str, ...] | list[str]) -> "ExecutionDiagnostics":
        return ExecutionDiagnostics(self.entries + tuple(diagnostics))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": EXECUTION_ARCHITECTURE_SCHEMA,
            "entries": list(self.entries),
        }


@dataclass(frozen=True)
class ExecutionFailure:
    failure_type: str
    message: str
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": EXECUTION_ARCHITECTURE_SCHEMA,
            "type": self.failure_type,
            "message": self.message,
            "diagnostics": list(self.diagnostics),
        }


@dataclass(frozen=True)
class CallFrame:
    frame_id: str
    function_name: str
    arguments: tuple[RuntimeValue, ...] = ()
    parameter_bindings: dict[str, RuntimeValue] = field(default_factory=dict)
    local_scope: dict[str, RuntimeValue] = field(default_factory=dict)
    return_target: str | None = None
    return_value: RuntimeValue | None = None
    status: str = CallFrameStatus.ACTIVE

    @staticmethod
    def create(
        frame_id: str,
        function_name: str,
        parameters: tuple[str, ...] | list[str] = (),
        arguments: tuple[RuntimeValue, ...] | list[RuntimeValue] = (),
        *,
        return_target: str | None = None,
    ) -> "CallFrame":
        args = tuple(arguments)
        names = tuple(parameters)
        bindings = {name: args[index] for index, name in enumerate(names) if index < len(args)}
        return CallFrame(
            frame_id=frame_id,
            function_name=function_name,
            arguments=args,
            parameter_bindings=bindings,
            local_scope=dict(bindings),
            return_target=return_target,
        )

    def bind_temporary(self, name: str, value: RuntimeValue) -> "CallFrame":
        scope = dict(self.local_scope)
        scope[name] = value
        return CallFrame(
            self.frame_id,
            self.function_name,
            self.arguments,
            dict(self.parameter_bindings),
            scope,
            self.return_target,
            self.return_value,
            self.status,
        )

    def returning(self, value: RuntimeValue | None) -> "CallFrame":
        return CallFrame(
            self.frame_id,
            self.function_name,
            self.arguments,
            dict(self.parameter_bindings),
            dict(self.local_scope),
            self.return_target,
            value,
            CallFrameStatus.RETURNING,
        )

    def completed(self) -> "CallFrame":
        return CallFrame(
            self.frame_id,
            self.function_name,
            self.arguments,
            dict(self.parameter_bindings),
            dict(self.local_scope),
            self.return_target,
            self.return_value,
            CallFrameStatus.COMPLETED,
        )

    def failed(self) -> "CallFrame":
        return CallFrame(
            self.frame_id,
            self.function_name,
            self.arguments,
            dict(self.parameter_bindings),
            dict(self.local_scope),
            self.return_target,
            self.return_value,
            CallFrameStatus.FAILED,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": EXECUTION_ARCHITECTURE_SCHEMA,
            "frame_id": self.frame_id,
            "function_name": self.function_name,
            "arguments": [runtime_value_to_plain(argument) for argument in self.arguments],
            "parameter_bindings": {
                name: runtime_value_to_plain(value)
                for name, value in sorted(self.parameter_bindings.items())
            },
            "local_scope": {
                name: runtime_value_to_plain(value)
                for name, value in sorted(self.local_scope.items())
            },
            "return_target": self.return_target,
            "return_value": runtime_value_to_plain(self.return_value),
            "status": self.status,
        }


@dataclass(frozen=True)
class CallStack:
    frames: tuple[CallFrame, ...] = ()
    max_depth: int = 64
    overflow_policy: str = "FailFast"

    def push(self, frame: CallFrame) -> "CallStack":
        if self.depth() >= self.max_depth:
            raise StackOverflow(f"maximum call stack depth exceeded: {self.max_depth}")
        return CallStack(self.frames + (frame,), self.max_depth, self.overflow_policy)

    def pop(self) -> tuple["CallStack", CallFrame]:
        if not self.frames:
            raise ExecutionArchitectureError("cannot pop an empty call stack")
        return CallStack(self.frames[:-1], self.max_depth, self.overflow_policy), self.frames[-1]

    def replace_current(self, frame: CallFrame) -> "CallStack":
        if not self.frames:
            raise ExecutionArchitectureError("cannot replace current frame on empty call stack")
        return CallStack(self.frames[:-1] + (frame,), self.max_depth, self.overflow_policy)

    def current(self) -> CallFrame | None:
        return self.frames[-1] if self.frames else None

    def depth(self) -> int:
        return len(self.frames)

    def is_empty(self) -> bool:
        return not self.frames

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": EXECUTION_ARCHITECTURE_SCHEMA,
            "max_depth": self.max_depth,
            "overflow_policy": self.overflow_policy,
            "frames": [frame.to_dict() for frame in self.frames],
        }


class ExecutionArchitectureError(RuntimeError):
    pass


class StackOverflow(ExecutionArchitectureError):
    pass


@dataclass(frozen=True)
class RuntimeResult:
    success: bool
    value: RuntimeValue | None = None
    diagnostics: tuple[str, ...] = ()
    trace: tuple[str, ...] = ()
    execution_plan: dict[str, Any] | None = None

    @staticmethod
    def failure(diagnostic: str) -> "RuntimeResult":
        return RuntimeResult(False, None, (diagnostic,))


class RuntimeOperationExecutor(Protocol):
    def search(self, request: RuntimeValue) -> RuntimeResult:
        ...

    def simulate(self, request: RuntimeValue) -> RuntimeResult:
        ...

    def predict(self, request: RuntimeValue) -> RuntimeResult:
        ...

    def plan(self, request: RuntimeValue) -> RuntimeResult:
        ...


@dataclass(frozen=True)
class SearchRequest:
    value: RuntimeValue


@dataclass(frozen=True)
class SimulationRequest:
    value: RuntimeValue


@dataclass(frozen=True)
class PredictionRequest:
    value: RuntimeValue


@dataclass(frozen=True)
class PlanningRequest:
    value: RuntimeValue


@dataclass(frozen=True)
class SearchResult:
    value: RuntimeValue
    trace: tuple[str, ...] = ()
    execution_plan: dict[str, Any] | None = None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class SimulationResult:
    value: RuntimeValue
    trace: tuple[str, ...] = ()
    execution_plan: dict[str, Any] | None = None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class PredictionResult:
    value: RuntimeValue
    trace: tuple[str, ...] = ()
    execution_plan: dict[str, Any] | None = None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanningResult:
    value: RuntimeValue
    trace: tuple[str, ...] = ()
    execution_plan: dict[str, Any] | None = None
    diagnostics: tuple[str, ...] = ()


class SearchEngine(Protocol):
    engine_name: str

    def search(self, request: SearchRequest) -> SearchResult:
        ...


class SimulationEngine(Protocol):
    engine_name: str

    def simulate(self, request: SimulationRequest) -> SimulationResult:
        ...


class PredictionEngine(Protocol):
    engine_name: str

    def predict(self, request: PredictionRequest) -> PredictionResult:
        ...


class PlanningEngine(Protocol):
    engine_name: str

    def plan(self, request: PlanningRequest) -> PlanningResult:
        ...


@dataclass(frozen=True)
class RuntimeEngineRegistry:
    search_engine: SearchEngine | None = None
    simulation_engine: SimulationEngine | None = None
    prediction_engine: PredictionEngine | None = None
    planning_engine: PlanningEngine | None = None
    backend: str = "RuntimeReal"


@dataclass(frozen=True)
class RuntimeEngineRegistryExecutor:
    registry: RuntimeEngineRegistry

    def search(self, request: RuntimeValue) -> RuntimeResult:
        if self.registry.search_engine is None:
            return RuntimeResult.failure(RuntimeIntegrationErrorCode.RUNTIME_ENGINE_MISSING)
        error = _validate_request_type("search", request)
        if error is not None:
            return RuntimeResult.failure(error)
        return _engine_result(
            self.registry.search_engine.search(SearchRequest(request))
        )

    def simulate(self, request: RuntimeValue) -> RuntimeResult:
        if self.registry.simulation_engine is None:
            return RuntimeResult.failure(RuntimeIntegrationErrorCode.RUNTIME_ENGINE_MISSING)
        error = _validate_request_type("simulate", request)
        if error is not None:
            return RuntimeResult.failure(error)
        return _engine_result(
            self.registry.simulation_engine.simulate(SimulationRequest(request))
        )

    def predict(self, request: RuntimeValue) -> RuntimeResult:
        if self.registry.prediction_engine is None:
            return RuntimeResult.failure(RuntimeIntegrationErrorCode.RUNTIME_ENGINE_MISSING)
        error = _validate_request_type("predict", request)
        if error is not None:
            return RuntimeResult.failure(error)
        return _engine_result(
            self.registry.prediction_engine.predict(PredictionRequest(request))
        )

    def plan(self, request: RuntimeValue) -> RuntimeResult:
        if self.registry.planning_engine is None:
            return RuntimeResult.failure(RuntimeIntegrationErrorCode.RUNTIME_ENGINE_MISSING)
        error = _validate_request_type("plan", request)
        if error is not None:
            return RuntimeResult.failure(error)
        return _engine_result(
            self.registry.planning_engine.plan(PlanningRequest(request))
        )


@dataclass(frozen=True)
class RuntimeOperationResult:
    operation: str
    language_value: RuntimeValue
    diagnostics: tuple[str, ...] = ()
    trace: tuple[str, ...] = ()
    execution_plan: dict[str, Any] | None = None
    engine: str | None = None


@dataclass(frozen=True)
class RuntimeExecutionReport:
    results: tuple[RuntimeOperationResult, ...]
    diagnostics: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionRequest:
    request_id: str
    source_module: str | None = None
    reason_ir: dict[str, Any] | None = None
    execution_plan: dict[str, Any] | None = None
    runtime_registry: RuntimeEngineRegistry | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": EXECUTION_ARCHITECTURE_SCHEMA,
            "request_id": self.request_id,
            "source_module": self.source_module,
            "reason_ir": self.reason_ir,
            "execution_plan": self.execution_plan,
            "runtime_registry": {
                "backend": self.runtime_registry.backend,
                "capabilities": _registry_capabilities(self.runtime_registry),
            }
            if self.runtime_registry is not None
            else None,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ExecutionResult:
    request_id: str
    status: str
    call_stack_trace: tuple[dict[str, Any], ...] = ()
    runtime_results: tuple[RuntimeOperationResult, ...] = ()
    diagnostics: tuple[str, ...] = ()
    trace: tuple[dict[str, Any], ...] = ()
    final_result: Any = None
    failure: ExecutionFailure | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": EXECUTION_ARCHITECTURE_SCHEMA,
            "request_id": self.request_id,
            "status": self.status,
            "call_stack_trace": list(self.call_stack_trace),
            "runtime_results": [
                {
                    "operation": result.operation,
                    "language_value": runtime_value_to_plain(result.language_value),
                    "diagnostics": list(result.diagnostics),
                    "trace": list(result.trace),
                    "execution_plan": result.execution_plan,
                    "engine": result.engine,
                }
                for result in self.runtime_results
            ],
            "diagnostics": list(self.diagnostics),
            "trace": list(self.trace),
            "final_result": self.final_result,
            "failure": self.failure.to_dict() if self.failure is not None else None,
        }


@dataclass(frozen=True)
class ExecutionCoordinator:
    runtime_registry: RuntimeEngineRegistry
    max_stack_depth: int = 64

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        trace: list[dict[str, Any]] = [
            _coordinator_trace("request_created", request_id=request.request_id)
        ]
        diagnostics: list[str] = []
        call_stack_trace: list[dict[str, Any]] = []

        validation_failure = self._validate_request(request)
        if validation_failure is not None:
            diagnostics.extend(validation_failure.diagnostics)
            trace.append(
                _coordinator_trace(
                    "diagnostic",
                    request_id=request.request_id,
                    diagnostic=validation_failure.message,
                )
            )
            return ExecutionResult(
                request.request_id,
                "failed",
                tuple(call_stack_trace),
                (),
                tuple(diagnostics),
                tuple(trace),
                None,
                validation_failure,
            )

        trace.append(_coordinator_trace("context_frozen", request_id=request.request_id))
        trace.append(_coordinator_trace("plan_validated", request_id=request.request_id))

        call_stack = CallStack(max_depth=self.max_stack_depth)
        try:
            frame = CallFrame.create(
                "frame-1",
                str(request.metadata.get("entry_function", "execution")),
                tuple(request.metadata.get("parameters", ())),
                tuple(request.metadata.get("arguments", ())),
                return_target=request.metadata.get("return_target"),
            )
            call_stack = call_stack.push(frame)
        except StackOverflow as error:
            failure = ExecutionFailure(
                ExecutionFailureType.STACK_OVERFLOW,
                str(error),
                (str(error),),
            )
            return ExecutionResult(
                request.request_id,
                "failed",
                tuple(call_stack_trace),
                (),
                failure.diagnostics,
                tuple(trace + [_coordinator_trace("stack_overflow", request_id=request.request_id)]),
                None,
                failure,
            )

        call_stack_trace.append(
            _call_stack_event("push", call_stack.current(), call_stack.depth())
        )
        trace.append(_coordinator_trace("call_stack_initialized", request_id=request.request_id))

        report = execute_runtime_operations_with_registry(
            request.reason_ir or {}, request.runtime_registry or self.runtime_registry
        )
        diagnostics.extend(report.diagnostics)
        for result in report.results:
            current = call_stack.current()
            if current is None:
                break
            current = current.bind_temporary(
                f"runtime.{result.operation}", result.language_value
            )
            call_stack = call_stack.replace_current(current)
            call_stack_trace.append(
                _call_stack_event("runtime_result", current, call_stack.depth(), result.operation)
            )
            trace.append(
                _coordinator_trace(
                    "runtime_call",
                    request_id=request.request_id,
                    operation=result.operation,
                    diagnostics=list(result.diagnostics),
                    trace=list(result.trace),
                )
            )

        current = call_stack.current()
        if current is not None:
            if diagnostics:
                current = current.failed()
                call_stack = call_stack.replace_current(current)
                call_stack_trace.append(
                    _call_stack_event("failed", current, call_stack.depth())
                )
            else:
                final_value = report.results[-1].language_value if report.results else None
                current = current.returning(final_value).completed()
                call_stack = call_stack.replace_current(current)
                call_stack_trace.append(
                    _call_stack_event("return", current, call_stack.depth())
                )
            call_stack, popped = call_stack.pop()
            call_stack_trace.append(_call_stack_event("pop", popped, call_stack.depth()))

        status = "failed" if diagnostics else "completed"
        failure = (
            ExecutionFailure(
                ExecutionFailureType.RUNTIME_FAILURE,
                "runtime execution produced diagnostics",
                tuple(diagnostics),
            )
            if diagnostics
            else None
        )
        final_result = _execution_final_result(report)
        trace.append(
            _coordinator_trace(
                "result_assembled",
                request_id=request.request_id,
                status=status,
                diagnostics=diagnostics,
            )
        )
        return ExecutionResult(
            request.request_id,
            status,
            tuple(call_stack_trace),
            report.results,
            tuple(diagnostics),
            tuple(trace),
            final_result,
            failure,
        )

    def _validate_request(self, request: ExecutionRequest) -> ExecutionFailure | None:
        diagnostics: list[str] = []
        if not request.request_id:
            diagnostics.append("EA1-003 request_id is required")
        if request.reason_ir is None or not isinstance(request.reason_ir, dict):
            diagnostics.append("EA1-003 Reason IR must be a dictionary")
        if request.execution_plan is not None:
            try:
                _validate_execution_plan(request.execution_plan)
            except ValueError as error:
                diagnostics.append(f"EA1-003 invalid ExecutionPlan: {error}")
        registry = request.runtime_registry or self.runtime_registry
        try:
            operations = _runtime_operations(request.reason_ir or {})
        except ValueError as error:
            operations = ()
            diagnostics.append(f"EA1-003 invalid Runtime metadata: {error}")
        for operation in operations:
            method = operation.get("operation") or operation.get("method")
            if method in RUNTIME_OPERATION_METHODS and _engine_name_for_operation(registry, method) is None:
                diagnostics.append(f"EA1-003 missing runtime capability: {method}")
        if self.max_stack_depth < 1:
            diagnostics.append("EA1-003 CallStack max_depth must be positive")
        if diagnostics:
            return ExecutionFailure(
                ExecutionFailureType.VALIDATION_FAILED,
                "coordinator validation failed",
                tuple(diagnostics),
            )
        return None


def execute_runtime_operations(
    reason_ir: dict[str, Any],
    executor: RuntimeOperationExecutor | RuntimeEngineRegistry | None,
) -> RuntimeExecutionReport:
    if isinstance(executor, RuntimeEngineRegistry):
        return execute_runtime_operations_with_registry(reason_ir, executor)
    operations = _runtime_operations(reason_ir)
    results: list[RuntimeOperationResult] = []
    diagnostics: list[str] = []

    for operation in operations:
        method = operation.get("operation") or operation.get("method")
        if method not in RUNTIME_OPERATION_METHODS:
            diagnostic = RuntimeIntegrationErrorCode.UNKNOWN_RUNTIME_OPERATION
            results.append(_none_result(str(method), diagnostic))
            diagnostics.append(diagnostic)
            continue
        if executor is None or not hasattr(executor, method):
            diagnostic = RuntimeIntegrationErrorCode.RUNTIME_BINDING_MISSING
            results.append(_none_result(method, diagnostic))
            diagnostics.append(diagnostic)
            continue
        try:
            argument = runtime_value_from_ir_expression(operation.get("argument"))
            argument = _coerce_reasoning_value(method, argument)
        except (TypeError, ValueError, KeyError) as error:
            diagnostic = (
                f"{RuntimeIntegrationErrorCode.ARGUMENT_CONVERSION_FAILED}: {error}"
            )
            results.append(_none_result(method, diagnostic))
            diagnostics.append(diagnostic)
            continue

        try:
            runtime_result = getattr(executor, method)(argument)
        except Exception as error:  # pragma: no cover - defensive integration edge.
            diagnostic = (
                f"{RuntimeIntegrationErrorCode.RUNTIME_EXECUTION_FAILED}: {error}"
            )
            results.append(_none_result(method, diagnostic))
            diagnostics.append(diagnostic)
            continue

        language_value, result_diagnostics = _language_optional(runtime_result)
        results.append(
            RuntimeOperationResult(
                method,
                language_value,
                result_diagnostics,
                runtime_result.trace,
                runtime_result.execution_plan,
            )
        )
        diagnostics.extend(result_diagnostics)

    metadata = {
        "runtime_operations_executed": [result.operation for result in results],
        "runtime_diagnostics": diagnostics,
    }
    return RuntimeExecutionReport(tuple(results), tuple(diagnostics), metadata)


def execute_runtime_operations_with_registry(
    reason_ir: dict[str, Any],
    registry: RuntimeEngineRegistry,
) -> RuntimeExecutionReport:
    executor = RuntimeEngineRegistryExecutor(registry)
    report = execute_runtime_operations(reason_ir, executor)
    runtime_execution = []
    diagnostics = list(report.diagnostics)
    results = []
    for result in report.results:
        engine_name = _engine_name_for_operation(registry, result.operation)
        if engine_name is None:
            diagnostics.append(RuntimeIntegrationErrorCode.RUNTIME_ENGINE_MISSING)
        if not result.trace:
            diagnostics.append(RuntimeIntegrationErrorCode.TRACE_MISSING)
        if result.execution_plan is not None:
            try:
                _validate_execution_plan(result.execution_plan)
            except ValueError as error:
                diagnostics.append(
                    f"{RuntimeIntegrationErrorCode.EXECUTION_PLAN_INCOMPATIBLE}: {error}"
                )
        runtime_execution.append(
            {
                "backend": registry.backend,
                "engine": engine_name or registry.backend,
                "operation": result.operation,
                "trace": list(result.trace),
                "diagnostics": list(result.diagnostics),
            }
        )
        results.append(
            RuntimeOperationResult(
                result.operation,
                result.language_value,
                result.diagnostics,
                result.trace,
                result.execution_plan,
                engine_name,
            )
        )
    metadata = {
        **report.metadata,
        "runtime_execution": runtime_execution,
        "runtime_diagnostics": diagnostics,
    }
    return RuntimeExecutionReport(tuple(results), tuple(diagnostics), metadata)


def runtime_value_from_ir_expression(value: Any) -> RuntimeValue:
    if value is None:
        raise ValueError("runtime operation argument is required")
    if not isinstance(value, dict):
        return _plain_value(value)
    if "schema_version" in value:
        _validate_execution_plan(value)
        return RuntimeValue.execution_plan(value)
    if "nodes" in value or "edges" in value:
        _validate_reason_graph(value)
        return RuntimeValue.reason_graph(value)
    node_type = value.get("node_type")
    if node_type == "ExpressionNode":
        return runtime_value_from_ir_expression(value["expression"])
    if node_type == "IdentifierNode":
        name = value["name"]
        lowered = name.lower()
        if lowered.endswith("goal") or lowered == "goal":
            return RuntimeValue.goal(name)
        if lowered.endswith("state") or lowered == "state":
            return RuntimeValue.state(name)
        if lowered.endswith("constraint") or lowered == "constraint":
            return RuntimeValue.constraint(name)
        if lowered.endswith("graph") or lowered == "reason_graph":
            return RuntimeValue.reason_graph({"id": name, "nodes": [], "edges": []})
        if lowered.endswith("plan") or lowered == "plan":
            return RuntimeValue.execution_plan(_execution_plan("argument", name))
        return RuntimeValue.string(name)
    if node_type == "StringLiteralNode":
        return RuntimeValue.string(value["value"])
    if node_type == "IntegerLiteralNode":
        return RuntimeValue.int(value["value"])
    if node_type == "FloatLiteralNode":
        return RuntimeValue.float(value["value"])
    if node_type == "BooleanLiteralNode":
        return RuntimeValue.bool(value["value"])
    if node_type in {"NullLiteralNode", "NoneLiteralNode"}:
        return RuntimeValue.optional(None)
    if node_type == "SomeExpressionNode":
        return RuntimeValue.optional(runtime_value_from_ir_expression(value["value"]))
    if node_type == "ArrayLiteralNode":
        return RuntimeValue.array(
            [runtime_value_from_ir_expression(item) for item in value["elements"]]
        )
    if node_type == "TupleLiteralNode":
        return RuntimeValue.array(
            [runtime_value_from_ir_expression(item) for item in value["elements"]]
        )
    if node_type == "StructLiteralNode":
        fields = {
            field["name"]: runtime_value_from_ir_expression(field["expression"])
            for field in value["fields"]
        }
        plain_fields = {
            name: runtime_value_to_plain(field)
            for name, field in fields.items()
        }
        type_name = value.get("type_name")
        if type_name == "Goal":
            return RuntimeValue.goal(str(plain_fields.get("name", "")))
        if type_name == "State":
            return RuntimeValue.state(str(plain_fields.get("id", "")))
        if type_name == "Constraint":
            return RuntimeValue.constraint(str(plain_fields.get("name", "")))
        if type_name == "ReasonGraph":
            return RuntimeValue.reason_graph(plain_fields)
        if type_name == "ExecutionPlan":
            _validate_execution_plan(plain_fields)
            return RuntimeValue.execution_plan(plain_fields)
        return RuntimeValue.struct(
            fields
        )
    if node_type == "MapLiteralNode":
        return RuntimeValue.reason_graph(
            {
                "entries": [
                    runtime_value_to_plain(runtime_value_from_ir_expression(entry))
                    for entry in value["entries"]
                ]
            }
        )
    if node_type == "MapEntryNode":
        return RuntimeValue.struct(
            {
                "key": runtime_value_from_ir_expression(value["key"]),
                "value": runtime_value_from_ir_expression(value["value"]),
            }
        )
    raise ValueError(f"unsupported runtime argument node: {node_type}")


def _coerce_reasoning_value(operation: str, value: RuntimeValue) -> RuntimeValue:
    if value.kind != "String":
        return value
    if not REASONING_IDENTIFIER.fullmatch(value.value):
        return value
    if operation in {"search", "plan"}:
        return RuntimeValue.goal(value.value)
    if operation == "predict":
        return RuntimeValue.state(value.value)
    if operation == "simulate":
        return RuntimeValue.execution_plan(_execution_plan("argument", value.value))
    return value


def runtime_value_to_plain(value: RuntimeValue | None) -> Any:
    if value is None:
        return None
    if value.kind in {"Bool", "Int", "Float", "String"}:
        return value.value
    if value.kind == "Struct":
        return {
            name: runtime_value_to_plain(field)
            for name, field in value.value.fields.items()
        }
    if value.kind == "Enum":
        return {
            "enum": value.value.enum_name,
            "value": value.value.value_name,
        }
    if value.kind == "Array":
        return [runtime_value_to_plain(item) for item in value.value]
    if value.kind == "Optional":
        return (
            {"some": runtime_value_to_plain(value.value)}
            if value.value is not None
            else {"none": True}
        )
    if value.kind in {
        "GoalValue",
        "StateValue",
        "ConstraintValue",
        "ReasonGraphValue",
        "ExecutionPlanValue",
    }:
        return value.value
    raise ValueError(f"unsupported runtime value kind: {value.kind}")


def runtime_real_registry() -> RuntimeEngineRegistry:
    return RuntimeEngineRegistry(
        search_engine=DeterministicSearchEngine("RuntimeReal"),
        simulation_engine=DeterministicSimulationEngine("RuntimeReal"),
        prediction_engine=DeterministicPredictionEngine("RuntimeReal"),
        planning_engine=DeterministicPlanningEngine("RuntimeReal"),
        backend="RuntimeReal",
    )


def hybrid_runtime_registry() -> RuntimeEngineRegistry:
    return RuntimeEngineRegistry(
        search_engine=DeterministicSearchEngine("HybridRuntime"),
        simulation_engine=DeterministicSimulationEngine("HybridRuntime"),
        prediction_engine=DeterministicPredictionEngine("HybridRuntime"),
        planning_engine=DeterministicPlanningEngine("HybridRuntime"),
        backend="HybridRuntime",
    )


class DeterministicSearchEngine:
    def __init__(self, backend: str):
        self.engine_name = f"{backend} SearchEngine"

    def search(self, request: SearchRequest) -> SearchResult:
        value = RuntimeValue.struct(
            {
                "goal": RuntimeValue.string(_request_label(request.value)),
                "found": RuntimeValue.bool(True),
                "cost": RuntimeValue.float(1.0),
                "confidence": RuntimeValue.float(1.0),
                "trace": RuntimeValue.array([RuntimeValue.string("search")]),
            }
        )
        return SearchResult(
            value,
            ("search:start", "search:complete"),
            _execution_plan("search", _request_label(request.value)),
        )


class DeterministicSimulationEngine:
    def __init__(self, backend: str):
        self.engine_name = f"{backend} SemanticSimulationEngine"

    def simulate(self, request: SimulationRequest) -> SimulationResult:
        value = RuntimeValue.struct(
            {
                "success": RuntimeValue.bool(True),
                "final_state": RuntimeValue.string(_request_label(request.value)),
                "confidence": RuntimeValue.float(1.0),
                "trace": RuntimeValue.array([RuntimeValue.string("simulate")]),
            }
        )
        return SimulationResult(value, ("simulate:start", "simulate:complete"))


class DeterministicPredictionEngine:
    def __init__(self, backend: str):
        self.engine_name = f"{backend} PredictionEngine"

    def predict(self, request: PredictionRequest) -> PredictionResult:
        value = RuntimeValue.struct(
            {
                "predicted_state": RuntimeValue.string(_request_label(request.value)),
                "confidence": RuntimeValue.float(1.0),
                "evidence": RuntimeValue.array([RuntimeValue.string("predict")]),
            }
        )
        return PredictionResult(value, ("predict:start", "predict:complete"))


class DeterministicPlanningEngine:
    def __init__(self, backend: str):
        self.engine_name = f"{backend} PlanningEngine"

    def plan(self, request: PlanningRequest) -> PlanningResult:
        label = _request_label(request.value)
        plan = _execution_plan("plan", label)
        value = RuntimeValue.struct(
            {
                "goal": RuntimeValue.string(label),
                "success": RuntimeValue.bool(True),
                "cost": RuntimeValue.float(1.0),
                "steps": RuntimeValue.array([RuntimeValue.string("step-1")]),
            }
        )
        return PlanningResult(value, ("plan:start", "plan:complete"), plan)


def _runtime_operations(reason_ir: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    metadata = reason_ir.get("metadata") or {}
    operations = metadata.get("runtime_operations") or ()
    if not isinstance(operations, list):
        raise ValueError("metadata.runtime_operations must be an array")
    return tuple(operation for operation in operations if isinstance(operation, dict))


def _engine_result(result: Any) -> RuntimeResult:
    return RuntimeResult(
        True,
        result.value,
        result.diagnostics,
        result.trace,
        result.execution_plan,
    )


def _language_optional(result: RuntimeResult) -> tuple[RuntimeValue, tuple[str, ...]]:
    diagnostics = list(result.diagnostics)
    if not result.success or result.value is None:
        if not result.success:
            diagnostics.append(RuntimeIntegrationErrorCode.RUNTIME_EXECUTION_FAILED)
        return RuntimeValue.optional(None), tuple(diagnostics)
    try:
        runtime_value_to_plain(result.value)
        return RuntimeValue.optional(result.value), tuple(diagnostics)
    except (TypeError, ValueError) as error:
        diagnostics.append(
            f"{RuntimeIntegrationErrorCode.RESULT_CONVERSION_FAILED}: {error}"
        )
        return RuntimeValue.optional(None), tuple(diagnostics)


def _none_result(operation: str, diagnostic: str) -> RuntimeOperationResult:
    return RuntimeOperationResult(
        operation,
        RuntimeValue.optional(None),
        (diagnostic,),
    )


def _engine_name_for_operation(
    registry: RuntimeEngineRegistry, operation: str
) -> str | None:
    engine = {
        "search": registry.search_engine,
        "simulate": registry.simulation_engine,
        "predict": registry.prediction_engine,
        "plan": registry.planning_engine,
    }.get(operation)
    return getattr(engine, "engine_name", None) if engine is not None else None


def _registry_capabilities(registry: RuntimeEngineRegistry) -> list[str]:
    return [
        operation
        for operation in ("search", "simulate", "predict", "plan")
        if _engine_name_for_operation(registry, operation) is not None
    ]


def _coordinator_trace(event_type: str, **fields: Any) -> dict[str, Any]:
    return {
        "schema": EXECUTION_ARCHITECTURE_SCHEMA,
        "event_type": event_type,
        **fields,
    }


def _call_stack_event(
    event_type: str,
    frame: CallFrame | None,
    depth: int,
    operation: str | None = None,
) -> dict[str, Any]:
    event = {
        "schema": EXECUTION_ARCHITECTURE_SCHEMA,
        "event_type": event_type,
        "depth": depth,
        "frame": frame.to_dict() if frame is not None else None,
    }
    if operation is not None:
        event["operation"] = operation
    return event


def _execution_final_result(report: RuntimeExecutionReport) -> dict[str, Any]:
    return {
        "runtime_operation_count": len(report.results),
        "runtime_operations": [result.operation for result in report.results],
        "runtime_values": [
            runtime_value_to_plain(result.language_value)
            for result in report.results
        ],
        "metadata": dict(report.metadata),
    }


def _validate_execution_plan(plan: dict[str, Any]) -> None:
    if plan.get("schema_version") != "execution-plan/0.1":
        raise ValueError("schema_version must be execution-plan/0.1")
    if not isinstance(plan.get("selected_steps"), list):
        raise ValueError("selected_steps must be an array")
    if "expected_cost" not in plan:
        raise ValueError("expected_cost is required")


def _validate_reason_graph(graph: dict[str, Any]) -> None:
    if not isinstance(graph.get("nodes", []), list):
        raise ValueError("reason graph nodes must be an array")
    if not isinstance(graph.get("edges", []), list):
        raise ValueError("reason graph edges must be an array")


def _validate_request_type(operation: str, value: RuntimeValue) -> str | None:
    allowed = {
        "search": {"GoalValue", "StateValue", "ConstraintValue", "ReasonGraphValue"},
        "simulate": {"ExecutionPlanValue", "ReasonGraphValue"},
        "predict": {"StateValue", "ReasonGraphValue"},
        "plan": {"GoalValue", "ConstraintValue", "ReasonGraphValue"},
    }[operation]
    if value.kind not in allowed:
        return (
            f"{RuntimeIntegrationErrorCode.REASONING_TYPE_CONVERSION_FAILED}: "
            f"{value.kind} cannot map to {operation} request"
        )
    try:
        if value.kind == "ExecutionPlanValue":
            _validate_execution_plan(value.value)
        if value.kind == "ReasonGraphValue":
            _validate_reason_graph(value.value)
    except ValueError as error:
        return (
            f"{RuntimeIntegrationErrorCode.REASONING_TYPE_CONVERSION_FAILED}: {error}"
        )
    return None


def _execution_plan(operation: str, target: str) -> dict[str, Any]:
    return {
        "schema_version": "execution-plan/0.1",
        "selected_steps": [
            {
                "step_id": f"{operation}-step-1",
                "transition_id": f"{operation}-transition",
                "source": "runtime",
                "target": target,
            }
        ],
        "alternative_paths": [],
        "expected_cost": 1.0,
        "evidence_refs": [f"{operation}:trace"],
        "planner_version": "runtime-integration/0.2",
    }


def _request_label(value: RuntimeValue) -> str:
    plain = runtime_value_to_plain(value)
    if isinstance(plain, dict):
        return str(plain.get("some") or plain.get("name") or plain)
    return str(plain)


def _plain_value(value: Any) -> RuntimeValue:
    if isinstance(value, bool):
        return RuntimeValue.bool(value)
    if isinstance(value, int):
        return RuntimeValue.int(value)
    if isinstance(value, float):
        return RuntimeValue.float(value)
    if isinstance(value, str):
        return RuntimeValue.string(value)
    if isinstance(value, list):
        return RuntimeValue.array([_plain_value(item) for item in value])
    if value is None:
        return RuntimeValue.optional(None)
    raise ValueError(f"unsupported runtime argument value: {value!r}")
