"""Deterministic Calculation surface-to-runtime lowering witness."""

from __future__ import annotations

import ast
import cmath
import json
import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


ARITHMETIC_TRANSITIONS = {
    ast.Add: "AddTransition",
    ast.Sub: "SubtractTransition",
    ast.Mult: "MultiplyTransition",
    ast.Div: "DivideTransition",
    ast.Pow: "PowerTransition",
    ast.Mod: "ModuloTransition",
}
MATHEMATICAL_TRANSITIONS = {
    "differentiate": "DifferentiateTransition",
    "integrate": "IntegrateTransition",
    "det": "DeterminantTransition",
    "inverse": "InverseTransition",
    "eigen": "EigenvalueTransition",
    "eigenvalues": "EigenvalueTransition",
    "simplify": "SimplifyTransition",
    "sqrt": "SquareRootTransition",
}
COMMUTATIVE = {"AddTransition", "MultiplyTransition"}
RESULT_STATUSES = {
    "Solved",
    "Partial",
    "Unresolved",
    "MultipleCandidates",
    "Contradiction",
    "Impossible",
}
INFERENCE_STATUS = {
    "Solved": "completed",
    "Partial": "decision_required",
    "Unresolved": "decision_required",
    "MultipleCandidates": "decision_required",
    "Contradiction": "rejected",
    "Impossible": "rejected",
}


class CalculationError(ValueError):
    pass


class DependencyCycleError(CalculationError):
    pass


class NumericPolicyError(CalculationError):
    pass


class NumericMode(str, Enum):
    REAL = "real"
    COMPLEX = "complex"


@dataclass(frozen=True)
class Expression:
    kind: str
    value: Any = None
    operands: tuple["Expression", ...] = ()

    @property
    def references(self) -> tuple[str, ...]:
        found: set[str] = set()

        def visit(node: Expression) -> None:
            if node.kind == "Reference":
                found.add(str(node.value))
            for operand in node.operands:
                visit(operand)

        visit(self)
        return tuple(sorted(found))

    def canonical(self) -> tuple[Any, ...]:
        children = tuple(operand.canonical() for operand in self.operands)
        if self.kind in COMMUTATIVE:
            children = tuple(sorted(children, key=repr))
        return (self.kind, _freeze(self.value), children)


@dataclass(frozen=True)
class Binding:
    binding_id: str
    name: str
    expression: Expression


@dataclass(frozen=True)
class Assignment:
    target: str
    expression: Expression


@dataclass(frozen=True)
class Decision:
    condition: Expression
    then_assignment: Assignment
    else_assignment: Assignment
    decision_kind: str = "if"


Statement = Binding | Assignment | Decision


@dataclass(frozen=True)
class Calculation:
    name: str
    goal: str
    statements: tuple[Statement, ...]


@dataclass(frozen=True)
class CalculationProgram:
    calculations: tuple[Calculation, ...]


@dataclass(frozen=True)
class BindingState:
    binding_id: str
    state_id: str
    name: str
    value: Any


@dataclass(frozen=True)
class CalculationTransition:
    transition_id: str
    relation: str
    source: str
    target: str
    inputs: tuple[str, ...]
    expression: tuple[Any, ...]
    guard: str | None = None


@dataclass(frozen=True)
class DependencyEdge:
    source_calculation: str
    target_calculation: str
    source_state: str


@dataclass(frozen=True)
class CalculationIR:
    calculation: str
    bindings: tuple[BindingState, ...]
    transitions: tuple[CalculationTransition, ...]
    result_state: str
    dependencies: tuple[DependencyEdge, ...]


@dataclass(frozen=True)
class LoweredProgram:
    calculations: tuple[CalculationIR, ...]
    reason_ir: Mapping[str, Any]
    execution_plan: Mapping[str, Any]


@dataclass(frozen=True)
class ResultState:
    status: str
    value: Any
    confidence: float
    trace: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in RESULT_STATUSES:
            raise CalculationError(f"unsupported result status: {self.status}")
        if not 0 <= self.confidence <= 1:
            raise CalculationError("confidence must be between zero and one")


def parse_expression(source: str) -> Expression:
    normalized = source.strip().replace("^", "**")
    try:
        node = ast.parse(normalized, mode="eval").body
    except SyntaxError as error:
        raise CalculationError(f"invalid expression: {source}") from error
    return _expression(node)


def parse_calculations(source: str) -> CalculationProgram:
    lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip() and not line.strip().startswith("//")
    ]
    calculations: list[Calculation] = []
    index = 0
    header = re.compile(
        r"^pub\s+calculation\s+([A-Za-z_]\w*)\s+goal:([A-Za-z_]\w*)\s*\{$"
    )
    while index < len(lines):
        match = header.match(lines[index])
        if not match:
            raise CalculationError(f"invalid calculation header: {lines[index]}")
        name, goal = match.groups()
        index += 1
        statements: list[Statement] = []
        while index < len(lines) and lines[index] != "}":
            if lines[index].startswith("if "):
                decision, index = _parse_decision(lines, index, name)
                statements.append(decision)
                continue
            statements.append(_parse_simple_statement(lines[index], name))
            index += 1
        if index >= len(lines):
            raise CalculationError(f"calculation {name} is missing closing brace")
        calculation = Calculation(name, goal, tuple(statements))
        _validate_calculation(calculation)
        calculations.append(calculation)
        index += 1
    names = [calculation.name for calculation in calculations]
    if len(names) != len(set(names)):
        raise CalculationError("calculation names must be unique")
    return CalculationProgram(tuple(calculations))


def _validate_calculation(calculation: Calculation) -> None:
    binding_names = [
        statement.name
        for statement in calculation.statements
        if isinstance(statement, Binding)
    ]
    if len(binding_names) != len(set(binding_names)):
        raise CalculationError(
            f"calculation {calculation.name} has duplicate binding names"
        )
    result_count = 0
    for statement in calculation.statements:
        if isinstance(statement, Assignment) and statement.target == "result":
            result_count += 1
        elif isinstance(statement, Decision):
            if statement.then_assignment.target == "result":
                result_count += 1
    if result_count != 1:
        raise CalculationError(
            f"calculation {calculation.name} requires exactly one result assignment"
        )


def _parse_decision(
    lines: list[str], index: int, calculation: str
) -> tuple[Decision, int]:
    match = re.match(r"^if\s+(.+)\s*\{$", lines[index])
    if not match:
        raise CalculationError(f"invalid if statement: {lines[index]}")
    condition = parse_expression(match.group(1))
    if index + 1 >= len(lines):
        raise CalculationError("if statement is missing a branch")
    then_assignment = _parse_assignment(lines[index + 1])
    index += 2
    if index >= len(lines) or lines[index] != "} else {":
        raise CalculationError("if statement requires an explicit else branch")
    if index + 2 >= len(lines):
        raise CalculationError("else statement is missing a branch")
    else_assignment = _parse_assignment(lines[index + 1])
    if lines[index + 2] != "}":
        raise CalculationError("else branch is missing closing brace")
    if then_assignment.target != else_assignment.target:
        raise CalculationError(
            f"decision branches in {calculation} must assign the same target"
        )
    return Decision(condition, then_assignment, else_assignment), index + 3


def _parse_simple_statement(line: str, calculation: str) -> Statement:
    if line.startswith("let "):
        assignment = _parse_assignment(line[4:])
        return Binding(
            f"{calculation}.binding.{assignment.target}",
            assignment.target,
            assignment.expression,
        )
    return _parse_assignment(line)


def _parse_assignment(line: str) -> Assignment:
    if "=" not in line:
        raise CalculationError(f"expected assignment: {line}")
    target, expression = line.split("=", 1)
    target = target.strip()
    if not re.match(r"^[A-Za-z_]\w*$", target):
        raise CalculationError(f"invalid assignment target: {target}")
    return Assignment(target, parse_expression(expression))


def lower_program(
    program: CalculationProgram, *, numeric_mode: NumericMode = NumericMode.REAL
) -> LoweredProgram:
    ordered = _topological_calculations(program)
    lowered: list[CalculationIR] = []
    all_transitions: list[CalculationTransition] = []
    initial_data: dict[str, Any] = {}
    result_states: dict[str, str] = {}
    previous_state: str | None = None

    for calculation in ordered:
        calculation_ir = _lower_calculation(
            calculation,
            result_states,
            entry_state=previous_state,
            numeric_mode=numeric_mode,
        )
        lowered.append(calculation_ir)
        all_transitions.extend(calculation_ir.transitions)
        result_states[calculation.name] = calculation_ir.result_state
        previous_state = calculation_ir.result_state
        for binding in calculation_ir.bindings:
            initial_data[f"{calculation.name}.{binding.name}"] = binding.value

    if not lowered:
        raise CalculationError("program requires at least one calculation")
    first_state = (
        all_transitions[0].source
        if all_transitions
        else lowered[0].result_state
    )
    final_state = lowered[-1].result_state
    reason_transitions = [
        {
            "transition_id": transition.transition_id,
            "source": transition.source,
            "relation": transition.relation,
            "target": transition.target,
            "expected_cost": 1.0,
            **({"guard": transition.guard} if transition.guard else {}),
            "effect": {
                "inputs": list(transition.inputs),
                "expression": _json_expression(transition.expression),
            },
        }
        for transition in all_transitions
    ]
    reason_ir = {
        "schema_version": "reason-ir/0.1",
        "initial_state": {
            "state_id": first_state,
            "state_type": "calculation",
            "data": {
                "bindings": initial_data,
                "numeric_mode": numeric_mode.value,
            },
        },
        "goal": {"kind": "reach_state", "target": final_state},
        "transitions": reason_transitions,
        "execution_policy": {
            "max_steps": max(1, len(reason_transitions)),
            "rollback_on_failure": True,
            "constraint_mode": "reject",
        },
        "trace_policy": {
            "level": "standard",
            "include_alternatives": True,
            "include_state_data": True,
        },
        "planner_policy": {
            "strategy": "calculation_topological_order",
            "max_depth": max(1, len(reason_transitions)),
            "max_alternatives": 8,
        },
        "metadata": {
            "calculation_semantics": "reasonscript-calculation-semantics/0.1",
            "calculation_order": [item.calculation for item in lowered],
        },
    }
    steps = [
        {
            "step_id": f"step-{index}",
            "transition_id": transition.transition_id,
            "source": transition.source,
            "target": transition.target,
        }
        for index, transition in enumerate(all_transitions, 1)
    ]
    execution_plan = {
        "selected_steps": steps,
        "alternative_paths": [],
        "expected_cost": float(len(steps)),
        "evidence_refs": [],
        "planner_version": "calculation-lowering/0.1",
    }
    return LoweredProgram(tuple(lowered), reason_ir, execution_plan)


def _lower_calculation(
    calculation: Calculation,
    known_results: Mapping[str, str],
    *,
    entry_state: str | None,
    numeric_mode: NumericMode,
) -> CalculationIR:
    bindings: list[BindingState] = []
    transitions: list[CalculationTransition] = []
    dependencies: set[DependencyEdge] = set()
    values: dict[str, Any] = {}
    current_state = entry_state or f"{calculation.name}.bindings"
    transition_count = 0
    result_state: str | None = None

    for statement in calculation.statements:
        if isinstance(statement, Binding):
            value = evaluate_expression(statement.expression, values, numeric_mode)
            values[statement.name] = value
            bindings.append(
                BindingState(
                    statement.binding_id,
                    f"{calculation.name}.state.{statement.name}",
                    statement.name,
                    value,
                )
            )
            continue
        if isinstance(statement, Decision):
            compare_target = f"{calculation.name}.decision.{transition_count + 1}"
            transition_count += 1
            transitions.append(
                CalculationTransition(
                    f"{calculation.name}.transition.{transition_count}.compare",
                    "CompareTransition",
                    current_state,
                    compare_target,
                    _resolved_inputs(
                        statement.condition, calculation.name, known_results, dependencies
                    ),
                    statement.condition.canonical(),
                )
            )
            selected = (
                statement.then_assignment
                if bool(evaluate_expression(statement.condition, values, numeric_mode))
                else statement.else_assignment
            )
            target_state = f"{calculation.name}.state.{selected.target}"
            transition_count += 1
            transitions.append(
                CalculationTransition(
                    f"{calculation.name}.transition.{transition_count}.decision",
                    "DecisionTransition",
                    compare_target,
                    target_state,
                    _resolved_inputs(
                        selected.expression, calculation.name, known_results, dependencies
                    ),
                    selected.expression.canonical(),
                    guard=repr(statement.condition.canonical()),
                )
            )
            values[selected.target] = evaluate_expression(
                selected.expression, values, numeric_mode
            )
            current_state = target_state
            if selected.target == "result":
                result_state = target_state
            continue

        transition_count += 1
        target_state = f"{calculation.name}.state.{statement.target}"
        transitions.append(
            CalculationTransition(
                f"{calculation.name}.transition.{transition_count}.{statement.target}",
                statement.expression.kind,
                current_state,
                target_state,
                _resolved_inputs(
                    statement.expression, calculation.name, known_results, dependencies
                ),
                statement.expression.canonical(),
            )
        )
        try:
            values[statement.target] = evaluate_expression(
                statement.expression, values, numeric_mode
            )
        except KeyError:
            # Calculation references are runtime dependencies, not local constants.
            values[statement.target] = None
        current_state = target_state
        if statement.target == "result":
            result_state = target_state

    if result_state is None:
        raise CalculationError(f"calculation {calculation.name} has no result assignment")
    return CalculationIR(
        calculation.name,
        tuple(bindings),
        tuple(transitions),
        result_state,
        tuple(sorted(dependencies, key=lambda edge: (edge.source_calculation, edge.target_calculation))),
    )


def evaluate_expression(
    expression: Expression,
    values: Mapping[str, Any],
    numeric_mode: NumericMode = NumericMode.REAL,
) -> Any:
    if expression.kind == "Literal":
        return expression.value
    if expression.kind == "Reference":
        return values[str(expression.value)]
    operands = [
        evaluate_expression(operand, values, numeric_mode)
        for operand in expression.operands
    ]
    if expression.kind == "AddTransition":
        return operands[0] + operands[1]
    if expression.kind == "SubtractTransition":
        return operands[0] - operands[1]
    if expression.kind == "MultiplyTransition":
        return operands[0] * operands[1]
    if expression.kind == "DivideTransition":
        return operands[0] / operands[1]
    if expression.kind == "PowerTransition":
        return operands[0] ** operands[1]
    if expression.kind == "ModuloTransition":
        return operands[0] % operands[1]
    if expression.kind == "CompareTransition":
        operator = expression.value
        return {
            "GreaterThan": operands[0] > operands[1],
            "GreaterThanOrEqual": operands[0] >= operands[1],
            "LessThan": operands[0] < operands[1],
            "LessThanOrEqual": operands[0] <= operands[1],
            "Equal": operands[0] == operands[1],
            "NotEqual": operands[0] != operands[1],
        }[operator]
    if expression.kind == "SquareRootTransition":
        value = operands[0]
        if numeric_mode == NumericMode.REAL and value < 0:
            raise NumericPolicyError("sqrt of a negative value is invalid in real mode")
        return math.sqrt(value) if numeric_mode == NumericMode.REAL else cmath.sqrt(value)
    if expression.kind in MATHEMATICAL_TRANSITIONS.values():
        return {"operation": expression.kind, "arguments": operands}
    raise CalculationError(f"expression is not directly evaluable: {expression.kind}")


def result_state(
    status: str,
    value: Any = None,
    *,
    confidence: float | None = None,
    trace: Iterable[str] = (),
) -> ResultState:
    if confidence is None:
        confidence = 1.0 if status == "Solved" else 0.0
    return ResultState(status, value, confidence, tuple(trace))


def structured_eigen_state(values: Iterable[Any], vectors: Iterable[Any]) -> ResultState:
    return result_state(
        "Solved",
        {"state_type": "EigenState", "values": list(values), "vectors": list(vectors)},
    )


def result_as_inference_dto(result: ResultState) -> dict[str, Any]:
    """Embed Calculation status semantics in the existing InferenceResult ABI."""
    return {
        "status": INFERENCE_STATUS[result.status],
        "final_state": {
            "state_id": "CalculationResult",
            "state_type": "calculation_result",
            "data": {
                "status": result.status,
                "value": _json_expression(result.value),
                "confidence": result.confidence,
                "trace": list(result.trace),
            },
        },
        "state_deltas": [],
        "proof": None,
        "violations": [],
        "alternatives": [],
        "trace_id": "calculation-result-trace",
    }


def _expression(node: ast.AST) -> Expression:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Expression("Literal", node.value)
    if isinstance(node, ast.Name):
        return Expression("Reference", node.id)
    if isinstance(node, ast.BinOp) and type(node.op) in ARITHMETIC_TRANSITIONS:
        return Expression(
            ARITHMETIC_TRANSITIONS[type(node.op)],
            operands=(_expression(node.left), _expression(node.right)),
        )
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return Expression(
            "SubtractTransition",
            operands=(Expression("Literal", 0), _expression(node.operand)),
        )
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        try:
            relation = MATHEMATICAL_TRANSITIONS[node.func.id]
        except KeyError as error:
            raise CalculationError(f"unsupported function: {node.func.id}") from error
        return Expression(relation, operands=tuple(_expression(arg) for arg in node.args))
    if isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators) == 1:
        operator = {
            ast.Gt: "GreaterThan",
            ast.GtE: "GreaterThanOrEqual",
            ast.Lt: "LessThan",
            ast.LtE: "LessThanOrEqual",
            ast.Eq: "Equal",
            ast.NotEq: "NotEqual",
        }.get(type(node.ops[0]))
        if operator:
            return Expression(
                "CompareTransition",
                operator,
                (_expression(node.left), _expression(node.comparators[0])),
            )
    raise CalculationError(f"unsupported expression node: {type(node).__name__}")


def _calculation_dependencies(calculation: Calculation, names: set[str]) -> set[str]:
    local_names = {
        statement.name
        for statement in calculation.statements
        if isinstance(statement, Binding)
    }
    dependencies: set[str] = set()
    for statement in calculation.statements:
        expressions: tuple[Expression, ...]
        if isinstance(statement, Binding):
            expressions = (statement.expression,)
        elif isinstance(statement, Assignment):
            expressions = (statement.expression,)
            local_names.add(statement.target)
        else:
            expressions = (
                statement.condition,
                statement.then_assignment.expression,
                statement.else_assignment.expression,
            )
            local_names.add(statement.then_assignment.target)
        for expression in expressions:
            dependencies.update(
                reference
                for reference in expression.references
                if reference in names and reference not in local_names
            )
    return dependencies


def _topological_calculations(program: CalculationProgram) -> tuple[Calculation, ...]:
    by_name = {calculation.name: calculation for calculation in program.calculations}
    dependencies = {
        name: _calculation_dependencies(calculation, set(by_name))
        for name, calculation in by_name.items()
    }
    ready = sorted(name for name, required in dependencies.items() if not required)
    ordered: list[Calculation] = []
    while ready:
        name = ready.pop(0)
        ordered.append(by_name[name])
        for candidate in sorted(dependencies):
            if name in dependencies[candidate]:
                dependencies[candidate].remove(name)
                if not dependencies[candidate] and by_name[candidate] not in ordered:
                    ready.append(candidate)
                    ready.sort()
        dependencies.pop(name, None)
    if dependencies:
        cycle = ", ".join(sorted(dependencies))
        raise DependencyCycleError(f"calculation dependency cycle: {cycle}")
    return tuple(ordered)


def _resolved_inputs(
    expression: Expression,
    calculation: str,
    known_results: Mapping[str, str],
    dependencies: set[DependencyEdge],
) -> tuple[str, ...]:
    inputs: list[str] = []
    for reference in expression.references:
        if reference in known_results:
            dependencies.add(
                DependencyEdge(reference, calculation, known_results[reference])
            )
            inputs.append(f"{reference}.result")
        else:
            inputs.append(f"{calculation}.{reference}")
    return tuple(sorted(inputs))


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _json_expression(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_expression(item) for item in value]
    if isinstance(value, complex):
        return {"real": value.real, "imaginary": value.imag}
    return value
