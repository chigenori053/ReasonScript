"""Projection from Surface AST to the validated semantic AST/compiler."""

from __future__ import annotations

from typing import Any

from frontend import ast as semantic
from frontend.compiler import compile as compile_semantic

from .nodes import (
    CalculationNode,
    AssignmentStatementNode,
    BinaryExpressionNode,
    BinaryOperator,
    CallExpressionNode,
    ComparisonExpressionNode,
    ExpressionNode,
    ConstraintNode,
    ExpressionStatementNode,
    GoalNode,
    GoalStatementNode,
    ImportNode,
    IfStatementNode,
    LetStatementNode,
    LogicalExpressionNode,
    MemberAccessNode,
    ModuleNode,
    ProgramNode,
    ReachStatementNode,
    RelationNode,
    RequireStatementNode,
    ResultStatementNode,
    TransitionNode,
    UnaryExpressionNode,
    to_json_value,
)
from .validation import validate


def project_program(program: ProgramNode) -> tuple[semantic.ModuleNode, ...]:
    validate(program)
    return tuple(project_module(module) for module in program.modules)


def project_module(module: ModuleNode) -> semantic.ModuleNode:
    declarations: list[Any] = []
    imports: list[str] = []
    surface_goals = [node for node in module.body if isinstance(node, GoalNode)]
    goal_target = surface_goals[0].name if surface_goals else f"{module.name}Result"
    declarations.append(
        semantic.GoalNode(f"{module.name}-goal", "reach_state", goal_target)
    )
    declarations.append(
        semantic.StateNode(
            f"{module.name}-state",
            f"{module.name}Start",
            "language_surface",
            {
                "module": module.name,
                "visibility": module.visibility.value,
                "declarations": [
                    type(node).__name__
                    for node in module.body
                    if not isinstance(node, ImportNode)
                ],
            },
        )
    )
    transition_index = 0
    for node in module.body:
        if isinstance(node, ImportNode):
            imports.append(".".join(node.path))
        elif isinstance(node, ConstraintNode):
            declarations.append(
                semantic.ConstraintNode(
                    f"{module.name}-constraint-{node.name}",
                    node.name,
                    "predicate",
                    node.name,
                )
            )
        elif isinstance(node, RelationNode):
            transition_index += 1
            declarations.append(
                semantic.TransitionNode(
                    f"{module.name}-relation-{transition_index}",
                    f"{module.name}-relation-{transition_index}",
                    node.source,
                    node.relation.value,
                    node.target,
                )
            )
        elif isinstance(node, TransitionNode):
            transition_index += 1
            requirements = [
                statement.constraint
                for statement in node.body
                if isinstance(statement, RequireStatementNode)
            ]
            goal_refs = [
                statement.goal
                for statement in node.body
                if isinstance(statement, GoalStatementNode)
            ]
            reaches = [
                statement.goal
                for statement in node.body
                if isinstance(statement, ReachStatementNode)
            ]
            declarations.append(
                semantic.TransitionNode(
                    f"{module.name}-transition-{transition_index}",
                    node.name,
                    node.from_state,
                    "Transition",
                    reaches[-1] if reaches else node.to_state,
                    guard=" && ".join(requirements) or None,
                    effect={
                        "goals": goal_refs,
                        "body": [to_json_value(item) for item in node.body],
                    },
                )
            )
        elif isinstance(node, CalculationNode):
            current = f"{module.name}Start"
            for index, statement in enumerate(node.body, 1):
                identifier, statement_data, relation = _statement_projection(
                    statement, index
                )
                if _terminates_with_result(statement):
                    identifier = "result"
                transition_index += 1
                target = (
                    (node.goal_annotation or goal_target)
                    if identifier == "result"
                    else f"{node.name}.{identifier}"
                )
                declarations.append(
                    semantic.TransitionNode(
                        f"{module.name}-calculation-{transition_index}",
                        f"{node.name}-{index}-{identifier}",
                        current,
                        relation,
                        target,
                        effect={
                            "calculation": node.name,
                            "visibility": node.visibility.value,
                            "goal_annotation": node.goal_annotation,
                            "target": identifier,
                            "statement": statement_data,
                            **(
                                {"expression": statement_data["expression"]}
                                if "expression" in statement_data
                                else {}
                            ),
                        },
                    )
                )
                current = target
    return semantic.ModuleNode(
        node_id=module.name,
        imports=tuple(imports),
        declarations=tuple(declarations),
        metadata=(
            semantic.MetadataNode(
                f"{module.name}-surface-version",
                "language_surface",
                "reasonscript-language-surface/0.1",
            ),
        ),
    )


def compile_program(program: ProgramNode) -> tuple[dict[str, Any], ...]:
    return tuple(compile_semantic(module) for module in project_program(program))


def execution_plan_for(reason_ir: dict[str, Any]) -> dict[str, Any]:
    steps = [
        {
            "step_id": f"step-{index}",
            "transition_id": transition["transition_id"],
            "source": transition["source"],
            "target": transition["target"],
        }
        for index, transition in enumerate(reason_ir["transitions"], 1)
    ]
    return {
        "selected_steps": steps,
        "alternative_paths": [],
        "expected_cost": sum(
            transition["expected_cost"] for transition in reason_ir["transitions"]
        ),
        "evidence_refs": [],
        "planner_version": "language-surface-validation/0.1",
    }


def _expression_relation(expression: ExpressionNode) -> str:
    value = expression.expression
    if isinstance(value, BinaryExpressionNode):
        return {
            BinaryOperator.ADD: "AddTransition",
            BinaryOperator.SUBTRACT: "SubtractTransition",
            BinaryOperator.MULTIPLY: "MultiplyTransition",
            BinaryOperator.DIVIDE: "DivideTransition",
            BinaryOperator.MODULO: "ModuloTransition",
        }[value.operator]
    if isinstance(value, ComparisonExpressionNode):
        return "CompareTransition"
    if isinstance(value, LogicalExpressionNode):
        return "LogicalTransition"
    if isinstance(value, UnaryExpressionNode):
        return "UnaryTransition"
    if isinstance(value, MemberAccessNode):
        return "MemberAccessTransition"
    if isinstance(value, CallExpressionNode):
        return "CallTransition"
    return "ExpressionTransition"


def _statement_projection(
    statement: Any, index: int
) -> tuple[str, dict[str, Any], str]:
    if isinstance(statement, LetStatementNode):
        return (
            statement.identifier,
            to_json_value(statement),
            _expression_relation(statement.expression),
        )
    if isinstance(statement, AssignmentStatementNode):
        return (
            statement.target,
            to_json_value(statement),
            "StateUpdateTransition",
        )
    if isinstance(statement, ResultStatementNode):
        return (
            "result",
            to_json_value(statement),
            "ResultTransition",
        )
    if isinstance(statement, ExpressionStatementNode):
        return (
            f"expression_{index}",
            to_json_value(statement),
            "CallTransition",
        )
    if isinstance(statement, IfStatementNode):
        return (f"if_{index}", to_json_value(statement), "DecisionTransition")
    return (
        f"match_{index}",
        to_json_value(statement),
        "DecisionTransition",
    )


def _terminates_with_result(statement: Any) -> bool:
    if isinstance(statement, ResultStatementNode):
        return True
    if isinstance(statement, IfStatementNode):
        if statement.else_branch is None:
            return False
        branches = [statement.body]
        branches.extend(branch.body for branch in statement.elif_branches)
        branches.append(statement.else_branch.body)
        return all(
            body and _terminates_with_result(body[-1]) for body in branches
        )
    if hasattr(statement, "arms"):
        return bool(statement.arms) and all(
            arm.body and _terminates_with_result(arm.body[-1])
            for arm in statement.arms
        )
    return False
