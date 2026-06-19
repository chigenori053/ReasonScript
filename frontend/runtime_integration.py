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
