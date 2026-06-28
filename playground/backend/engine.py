"""ReasonScript Playground — ExecutionPlan / Simulation / Knowledge engines."""

from __future__ import annotations

import copy
from typing import Any

# ---------------------------------------------------------------------------
# ExecutionPlan engine
# ---------------------------------------------------------------------------

def build_execution_plan(ir: dict[str, Any]) -> dict[str, Any]:
    """
    Derive an ExecutionPlan from a Reason IR via BFS path search.

    Returns a dict conforming to execution-plan/0.1 schema, augmented with
    playground summary fields (goal, distance, reachable).
    """
    goal_target = ir.get("goal", {}).get("target", "")
    initial_id = ir.get("initial_state", {}).get("state_id", "")
    transitions = ir.get("transitions", [])
    max_depth = ir.get("planner_policy", {}).get("max_depth", 128)

    # Build adjacency list
    adj: dict[str, list[dict[str, Any]]] = {}
    all_sources: set[str] = set()
    all_targets: set[str] = set()
    for t in transitions:
        adj.setdefault(t["source"], []).append(t)
        all_sources.add(t["source"])
        all_targets.add(t["target"])

    # If the initial_state_id has no outgoing transitions (Language Surface module IR),
    # use the set of sources that are not targets as entry points.
    if initial_id not in adj and transitions:
        roots = all_sources - all_targets
        initial_id = next(iter(roots)) if roots else transitions[0]["source"]

    # BFS to find shortest path to goal (graph node search)
    from collections import deque
    queue: deque[tuple[str, list[dict[str, Any]], float]] = deque()
    queue.append((initial_id, [], 0.0))
    visited: set[str] = {initial_id}
    found_path: list[dict[str, Any]] = []
    found_cost = 0.0
    reachable = False

    # Also collect ALL reachable paths (for semantic-goal IR where goal is not a graph node)
    all_paths: list[tuple[list[dict[str, Any]], float]] = []

    bfs_queue: deque[tuple[str, list[dict[str, Any]], float]] = deque([(initial_id, [], 0.0)])
    bfs_visited: set[str] = {initial_id}
    while bfs_queue:
        current, path, cost = bfs_queue.popleft()
        if path:
            all_paths.append((path, cost))
        if current == goal_target and not reachable:
            found_path = path
            found_cost = cost
            reachable = True
        if len(path) >= max_depth:
            continue
        for t in adj.get(current, []):
            if not _branch_transition_matches(t):
                continue
            if t["target"] not in bfs_visited:
                bfs_visited.add(t["target"])
                bfs_queue.append((t["target"], path + [t], cost + t.get("expected_cost", 1.0)))

    # If goal_target not in transition graph (Language Surface semantic goal),
    # use longest reachable path as the plan
    if not reachable and all_paths:
        found_path, found_cost = max(all_paths, key=lambda x: len(x[0]))
        # Semantic goal: the module's GoalNode exists in the IR but not in the graph
        reachable = True  # plan exists, goal is a semantic construct

    selected_steps = [
        {
            "step_id": f"step-{i + 1}",
            "transition_id": t["transition_id"],
            "source": t["source"],
            "target": t["target"],
        }
        for i, t in enumerate(found_path)
    ]
    selected_return = _selected_return_transition_id(found_path)
    selected_branches = _selected_branches_for_transition(selected_return)

    # Build alternative paths (up to 3 shortest)
    alt_candidates = sorted(
        [p for p, _ in all_paths if p != found_path],
        key=len,
    )[:3]
    alternative_paths = [
        {
            "step_ids": [f"alt-step-{i + 1}" for i in range(len(p))],
            "expected_cost": sum(t.get("expected_cost", 1.0) for t in p),
        }
        for p in alt_candidates
    ]

    return {
        "schema_version": "execution-plan/0.1",
        "goal": goal_target,
        "reachable": reachable,
        "distance": len(selected_steps),
        "selected_steps": selected_steps,
        "selected_branch": selected_return,
        "selected_branches": selected_branches,
        "path_signature": selected_return or _path_signature(selected_branches),
        "alternative_paths": alternative_paths,
        "expected_cost": found_cost,
        "evidence_refs": [],
        "planner_version": "playground-planner/0.2",
    }


# ---------------------------------------------------------------------------
# Simulation engine
# ---------------------------------------------------------------------------

def simulate(ir: dict[str, Any]) -> dict[str, Any]:
    """
    Execute Reason IR and return a SemanticSimulation result.

    Follows the same logic as conformance.framework.execute_reason_ir but
    returns a richer playground-friendly structure.
    """
    ir_norm = copy.deepcopy(ir)
    goal_target = ir_norm.get("goal", {}).get("target", "")
    transitions = ir_norm.get("transitions", [])
    constraints = ir_norm.get("constraints", [])
    max_steps = ir_norm.get("execution_policy", {}).get("max_steps", 128)

    # Resolve effective initial state (same logic as build_execution_plan)
    initial_state_raw = copy.deepcopy(ir_norm.get("initial_state", {}))
    initial_id = initial_state_raw.get("state_id", "")
    all_sources = {t["source"] for t in transitions}
    all_targets = {t["target"] for t in transitions}
    if initial_id not in all_sources and transitions:
        roots = all_sources - all_targets
        initial_id = next(iter(roots)) if roots else transitions[0]["source"]

    current = {"state_id": initial_id, "state_type": initial_state_raw.get("state_type", ""), "data": {}}

    # Constraint check (simple expression name match against initial data)
    violations = [
        c["constraint_id"]
        for c in constraints
        if not _constraint_passes(c.get("expression", ""), initial_state_raw.get("data", {}))
    ]

    trace: list[dict[str, Any]] = [{"step": 0, "state": initial_id, "event": "start"}]
    applied: list[str] = []
    total_cost = 0.0

    if not violations:
        for t in transitions:
            if len(applied) >= max_steps:
                break
            if t["source"] != current.get("state_id"):
                continue
            if not _branch_transition_matches(t):
                continue
            current = {
                "state_id": t["target"],
                "state_type": current.get("state_type", ""),
                "data": copy.deepcopy(t.get("effect", {"identity": t["target"]})),
            }
            applied.append(t["transition_id"])
            total_cost += t.get("expected_cost", 1.0)
            if t.get("relation") == "FunctionReturnTransition":
                branch_event = _branch_selection_event(t)
                for comparison_event in branch_event.pop("comparison_evaluations", []):
                    trace.append({
                        "step": len(applied),
                        "state": t["target"],
                        "transition": t["transition_id"],
                        "event": "comparison_evaluation",
                        **comparison_event,
                    })
                for match_event in branch_event.pop("match_evaluations", []):
                    match_event["selected_branch"] = t["transition_id"]
                    trace.append({
                        "step": len(applied),
                        "state": t["target"],
                        "transition": t["transition_id"],
                        "event": "match_evaluation",
                        **match_event,
                    })
                for alternative_event in branch_event.pop("alternative_evaluations", []):
                    alternative_event["selected_branch"] = t["transition_id"]
                    trace.append({
                        "step": len(applied),
                        "state": t["target"],
                        "transition": t["transition_id"],
                        "event": "alternative_pattern_evaluation",
                        **alternative_event,
                    })
                for guard_event in branch_event.pop("guard_evaluations", []):
                    guard_event["selected_branch"] = t["transition_id"]
                    trace.append({
                        "step": len(applied),
                        "state": t["target"],
                        "transition": t["transition_id"],
                        "event": "guard_evaluation",
                        **guard_event,
                    })
                for pattern_decision in branch_event.pop("pattern_decisions", []):
                    trace.append({
                        "step": len(applied),
                        "state": t["target"],
                        "transition": t["transition_id"],
                        "event": "pattern_decision",
                        "event_type": "PatternDecision",
                        **pattern_decision,
                    })
                for selection in _branch_selection_events(t):
                    trace.append({
                        "step": len(applied),
                        "state": t["target"],
                        "transition": t["transition_id"],
                        "event": "branch_selection",
                        "event_type": "BranchSelection",
                        **selection,
                        **branch_event,
                    })
            trace.append({
                "step": len(applied),
                "state": t["target"],
                "transition": t["transition_id"],
                "event": "transition",
            })

    final_state_id = current.get("state_id", "")
    goal_reached_direct = final_state_id == goal_target
    # Semantic goal: GoalNode name not in graph but transitions completed
    semantic_goal = not goal_reached_direct and bool(applied) and not violations
    goal_reached = goal_reached_direct or semantic_goal
    success = goal_reached and not violations

    # Confidence: degrades with cost; semantic goals slightly lower
    base = 0.92 if not semantic_goal else 0.82
    confidence = round(max(0.3, base - total_cost * 0.04), 2) if success else 0.0
    selected_branches = [
        item["branch"]
        for item in trace
        if item.get("event_type") == "BranchSelection" and item.get("branch")
    ]
    selected_return = next(
        (
            item.get("transition")
            for item in trace
            if item.get("event_type") == "BranchSelection" and item.get("transition")
        ),
        None,
    )

    return {
        "schema_version": "semantic-simulation/0.2",
        "success": success,
        "goal_reached": goal_reached,
        "cost": total_cost,
        "confidence": confidence,
        "final_state": current.get("state_id", ""),
        "step_count": len(applied),
        "selected_branch": selected_return,
        "selected_branches": selected_branches,
        "path_signature": selected_return or _path_signature(selected_branches),
        "violations": violations,
        "trace": trace,
    }


def _constraint_passes(expression: str, data: Any) -> bool:
    """Conservative constraint check: unknown expressions pass."""
    if not expression:
        return True
    if isinstance(data, dict):
        return expression not in data.get("violated", [])
    return True


def _branch_transition_matches(transition: dict[str, Any]) -> bool:
    if transition.get("relation") != "FunctionReturnTransition":
        return True
    effect = transition.get("effect") or {}
    conditions = effect.get("branch_conditions") or []
    context = effect.get("evaluation_context") or {}
    for condition in conditions:
        expected = condition.get("expected_value")
        actual = _evaluate_bool_condition(condition, context)
        if actual is None or actual != expected:
            return False
    match_conditions = effect.get("match_conditions") or []
    pattern_decisions = effect.get("pattern_decisions") or []
    if pattern_decisions and not all(decision.get("matched") for decision in pattern_decisions):
        return False
    for index, condition in enumerate(match_conditions):
        value = _match_value(condition, context)
        pattern = condition.get("pattern")
        if _is_catch_all_pattern(pattern):
            previous_patterns = [
                item.get("pattern")
                for item in match_conditions[:index]
                if not _is_catch_all_pattern(item.get("pattern"))
            ]
            if any(_match_pattern_matches(value, previous) for previous in previous_patterns):
                return False
            if not _guard_matches(condition, context):
                return False
            continue
        if not _match_pattern_matches(value, pattern):
            return False
        _bind_optional_pattern(value, pattern, context)
        _bind_struct_pattern(value, pattern, context)
        if not _guard_matches(condition, context):
            return False
    return True


def _evaluate_bool_condition(
    condition: dict[str, Any],
    context: dict[str, Any],
) -> bool | None:
    comparison = condition.get("comparison")
    if comparison is not None:
        value = _evaluate_comparison(comparison, context)
        return value if isinstance(value, bool) else None
    expression = condition.get("expression")
    value = _expression_value(expression, context)
    return value if isinstance(value, bool) else None


def _evaluate_comparison(
    comparison: dict[str, Any],
    context: dict[str, Any],
) -> bool | None:
    operator = comparison.get("operator")
    left = _comparison_operand_value(comparison.get("left"), context)
    right = _comparison_operand_value(comparison.get("right"), context)
    if left is None or right is None:
        return None
    if type(left) is not type(right):
        if not (
            isinstance(left, (int, float))
            and not isinstance(left, bool)
            and isinstance(right, (int, float))
            and not isinstance(right, bool)
        ):
            return None
    if isinstance(left, bool) or isinstance(right, bool):
        if operator == "==":
            return left is right
        if operator == "!=":
            return left is not right
        return None
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if operator == ">":
            return left > right
        if operator == "<":
            return left < right
        if operator == ">=":
            return left >= right
        if operator == "<=":
            return left <= right
        if operator == "==":
            return left == right
        if operator == "!=":
            return left != right
    return None


def _comparison_operand_value(operand: Any, context: dict[str, Any]) -> Any:
    if isinstance(operand, str):
        return context.get(operand)
    if isinstance(operand, (bool, int, float)):
        return operand
    return _expression_value(operand, context)


def _expression_value(expression: Any, context: dict[str, Any]) -> Any:
    if not isinstance(expression, dict):
        return None
    node_type = expression.get("node_type")
    if node_type == "ExpressionNode":
        return _expression_value(expression.get("expression"), context)
    if node_type == "IdentifierNode":
        return context.get(expression.get("name"))
    if node_type == "BooleanLiteralNode":
        return expression.get("value")
    if node_type in {"IntegerLiteralNode", "FloatLiteralNode"}:
        return expression.get("value")
    if node_type == "ComparisonExpressionIRNode":
        return _evaluate_comparison(expression, context)
    if node_type == "GuardExpressionIRNode":
        comparison = expression.get("comparison")
        if comparison is not None:
            return _evaluate_comparison(comparison, context)
        return _expression_value(expression.get("expression_ast"), context)
    if node_type == "ComparisonExpressionNode":
        return _evaluate_comparison(
            {
                "operator": _surface_comparison_operator(expression.get("operator")),
                "left": expression.get("left"),
                "right": expression.get("right"),
            },
            context,
        )
    return None


def _match_value(condition: dict[str, Any], context: dict[str, Any]) -> Any:
    value_name = condition.get("value")
    if isinstance(value_name, str) and value_name in context:
        return context[value_name]
    return _expression_value(condition.get("expression"), context)


def _match_pattern_matches(value: Any, pattern: Any) -> bool:
    if _is_catch_all_pattern(pattern):
        return True
    if _is_enum_pattern(pattern):
        enum_value = _enum_match_value(value)
        if enum_value is None:
            return False
        return (
            enum_value.get("enum") == pattern.get("enum_name")
            and enum_value.get("variant") == pattern.get("value_name")
        )
    if _is_optional_pattern(pattern):
        optional_value = _optional_match_value(value)
        if optional_value is None:
            return False
        if pattern.get("node_type") == "OptionalSomePatternNode":
            if optional_value.get("kind") != "some":
                return False
            inner_pattern = pattern.get("pattern")
            if inner_pattern is None:
                return True
            return _struct_field_pattern_matches(optional_value.get("value"), inner_pattern)
        return optional_value.get("kind") == "none"
    if _is_or_pattern(pattern):
        return any(
            _match_pattern_matches(value, alternative)
            for alternative in pattern.get("alternatives") or []
        )
    if _is_struct_pattern(pattern):
        return _struct_pattern_matches(value, pattern)
    return value == pattern


def _is_enum_pattern(pattern: Any) -> bool:
    return isinstance(pattern, dict) and pattern.get("node_type") == "EnumValuePatternNode"


def _is_struct_pattern(pattern: Any) -> bool:
    return isinstance(pattern, dict) and pattern.get("node_type") == "StructPatternNode"


def _is_optional_pattern(pattern: Any) -> bool:
    return (
        isinstance(pattern, dict)
        and pattern.get("node_type")
        in {"OptionalSomePatternNode", "OptionalNonePatternNode"}
    )


def _is_or_pattern(pattern: Any) -> bool:
    return isinstance(pattern, dict) and pattern.get("node_type") == "OrPatternIRNode"


def _is_catch_all_pattern(pattern: Any) -> bool:
    return pattern in {"default", "wildcard"} if isinstance(pattern, str) else False


def _enum_match_value(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    if isinstance(value.get("enum"), str) and isinstance(value.get("variant"), str):
        return {"enum": value["enum"], "variant": value["variant"]}
    if isinstance(value.get("enum_name"), str):
        variant = value.get("variant") or value.get("variant_name") or value.get("value_name")
        if isinstance(variant, str):
            return {"enum": value["enum_name"], "variant": variant}
    return None


def _optional_match_value(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if value.get("kind") == "some":
        return {"kind": "some", "value": value.get("value")}
    if value.get("kind") == "none":
        return {"kind": "none"}
    if value.get("node_type") == "SomeExpressionNode":
        return {"kind": "some", "value": _expression_value(value.get("value"), {})}
    if value.get("node_type") == "NoneLiteralNode":
        return {"kind": "none"}
    return None


def _bind_optional_pattern(
    value: Any,
    pattern: Any,
    context: dict[str, Any],
) -> None:
    if not (
        _is_optional_pattern(pattern)
        and pattern.get("node_type") == "OptionalSomePatternNode"
        and isinstance(pattern.get("binding"), str)
    ):
        return
    optional_value = _optional_match_value(value)
    if optional_value is not None and optional_value.get("kind") == "some":
        context[pattern["binding"]] = optional_value.get("value")


def _struct_pattern_matches(value: Any, pattern: dict[str, Any]) -> bool:
    if not isinstance(value, dict):
        return False
    if (
        value.get("struct_type") != pattern.get("type_name")
        and value.get("type_name") != pattern.get("type_name")
    ):
        return False
    fields = value.get("fields")
    if not isinstance(fields, dict):
        return False
    for field in pattern.get("fields") or []:
        field_name = field.get("field_name")
        if field_name not in fields:
            return False
        if not _struct_field_pattern_matches(fields[field_name], field.get("pattern")):
            return False
    return True


def _struct_field_pattern_matches(value: Any, pattern: Any) -> bool:
    if not isinstance(pattern, dict):
        return value == pattern
    node_type = pattern.get("node_type")
    if node_type == "WildcardPatternNode":
        return True
    if node_type == "DefaultPatternNode":
        return False
    if node_type == "StructBindingPatternNode":
        return True
    if node_type == "IdentifierPatternNode":
        return True
    if node_type == "OrPatternNode":
        return any(
            _struct_field_pattern_matches(value, alternative)
            for alternative in pattern.get("alternatives") or []
        )
    if node_type == "StructPatternNode":
        return _struct_pattern_matches(value, pattern)
    if node_type == "QualifiedPatternNode":
        enum_value = _enum_match_value(value)
        return enum_value == {
            "enum": pattern.get("namespace"),
            "variant": pattern.get("identifier"),
        }
    if node_type == "EnumValuePatternNode":
        enum_value = _enum_match_value(value)
        return enum_value == {
            "enum": pattern.get("enum_name"),
            "variant": pattern.get("value_name"),
        }
    if node_type == "LiteralPatternNode":
        literal = pattern.get("value")
        if isinstance(literal, dict) and "value" in literal:
            return value == literal["value"]
        return value == literal
    return value == pattern


def _guard_matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    guard = condition.get("guard")
    if guard is None:
        return True
    return _expression_value(guard, context) is True


def _bind_struct_pattern(
    value: Any,
    pattern: Any,
    context: dict[str, Any],
) -> None:
    if not _is_struct_pattern(pattern) or not isinstance(value, dict):
        return
    fields = value.get("fields")
    if not isinstance(fields, dict):
        return
    for field in pattern.get("fields") or []:
        if not isinstance(field, dict):
            continue
        field_name = field.get("field_name")
        if not isinstance(field_name, str) or field_name not in fields:
            continue
        field_pattern = field.get("pattern")
        if not isinstance(field_pattern, dict):
            continue
        if field_pattern.get("node_type") == "StructBindingPatternNode":
            binding = field_pattern.get("binding")
            if isinstance(binding, str):
                context[binding] = fields[field_name]
        elif field_pattern.get("node_type") == "IdentifierPatternNode":
            binding = field_pattern.get("name")
            if isinstance(binding, str):
                context[binding] = fields[field_name]
        elif field_pattern.get("node_type") == "StructPatternNode":
            _bind_struct_pattern(fields[field_name], field_pattern, context)


def _branch_selection_event(transition: dict[str, Any]) -> dict[str, Any]:
    effect = transition.get("effect") or {}
    conditions = effect.get("branch_conditions") or []
    match_conditions = effect.get("match_conditions") or []
    pattern_decisions = effect.get("pattern_decisions") or []
    context = effect.get("evaluation_context") or {}
    evaluated = [
        {
            "condition": condition.get("condition"),
            "value": _evaluate_bool_condition(condition, context),
        }
        for condition in conditions
    ]
    comparison_events = [
        _comparison_evaluation_event(condition, context)
        for condition in conditions
        if condition.get("comparison") is not None
    ]
    match_events = [
        _match_evaluation_event(condition, context)
        for condition in match_conditions
    ]
    alternative_events = [
        event
        for condition in match_conditions
        for event in _alternative_pattern_evaluation_events(condition, context)
    ]
    guard_events = [
        _guard_evaluation_event(condition, context)
        for condition in match_conditions
        if condition.get("guard") is not None
    ]
    if not evaluated and not match_events:
        return {}
    result = {
        "condition": evaluated[-1]["condition"] if evaluated else None,
        "value": evaluated[-1]["value"] if evaluated else None,
        "conditions": evaluated,
    }
    if comparison_events:
        result["comparison_evaluations"] = comparison_events
        result["comparison_evidence"] = {
            "expression": comparison_events[-1]["expression"],
            "result": comparison_events[-1]["result"],
        }
    if match_events:
        result["match_evaluations"] = match_events
        result["match_evidence"] = {
            "value": match_events[-1]["value"],
            "matched_case": match_events[-1]["selected_case"],
        }
    if alternative_events:
        result["alternative_evaluations"] = alternative_events
        result["or_pattern_evidence"] = {
            "selected_alternative": alternative_events[-1]["alternative_index"],
            "selected_case": alternative_events[-1]["selected_case"],
            "attempted": len(alternative_events),
        }
    if guard_events:
        result["guard_evaluations"] = guard_events
        result["guard_evidence"] = {
            "expression": guard_events[-1]["expression"],
            "result": guard_events[-1]["result"],
        }
    if pattern_decisions:
        result["pattern_decisions"] = pattern_decisions
        result["pattern_evidence"] = _pattern_decision_evidence(pattern_decisions[-1])
    return result


def _branch_selection_events(transition: dict[str, Any]) -> list[dict[str, Any]]:
    transition_id = transition.get("transition_id")
    branches = _selected_branches_for_transition(transition_id)
    if not branches:
        return []
    if len(branches) == 1:
        return [{"branch": branches[0]}]
    return [
        {
            "branch": branch,
            "depth": index,
            "path_signature": transition_id,
        }
        for index, branch in enumerate(branches)
    ]


def _match_evaluation_event(
    condition: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    value = _match_value(condition, context)
    pattern = condition.get("pattern")
    if _is_enum_pattern(pattern):
        enum_value = _enum_match_value(value) or {}
        return {
            "event_type": "EnumPatternEvaluation",
            "enum_name": pattern.get("enum_name"),
            "input_variant": enum_value.get("variant"),
            "pattern_variant": pattern.get("value_name"),
            "result": _match_pattern_matches(value, pattern),
            "value": value,
            "selected_case": _enum_pattern_signature(pattern),
            "selected_branch": condition.get("target"),
        }
    if _is_optional_pattern(pattern):
        optional_value = _optional_match_value(value) or {}
        kind = str(optional_value.get("kind") or "").lower()
        return {
            "event_type": "OptionalPatternEvaluation",
            "kind": kind or None,
            "result": _match_pattern_matches(value, pattern),
            "value": value,
            "selected_case": _optional_pattern_signature(pattern),
            "selected_branch": condition.get("target"),
        }
    if _is_struct_pattern(pattern):
        return {
            "event_type": "StructPatternEvaluation",
            "struct": pattern.get("type_name"),
            "matched_fields": _struct_pattern_matched_fields(pattern),
            "result": _match_pattern_matches(value, pattern),
            "value": value,
            "selected_case": _struct_pattern_signature(pattern),
            "selected_branch": condition.get("target"),
        }
    return {
        "event_type": "MatchEvaluation",
        "value": value,
        "selected_case": pattern,
        "selected_branch": condition.get("target"),
    }


def _alternative_pattern_evaluation_events(
    condition: dict[str, Any],
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    or_pattern = condition.get("or_pattern")
    if not isinstance(or_pattern, dict):
        return []
    alternatives = or_pattern.get("alternatives") or []
    selected_index = or_pattern.get("selected_index")
    if not isinstance(selected_index, int):
        selected_index = len(alternatives) - 1
    value = _match_value(condition, context)
    events: list[dict[str, Any]] = []
    for index, alternative in enumerate(alternatives[: selected_index + 1]):
        result = _match_pattern_matches(value, alternative)
        events.append(
            {
                "event_type": "AlternativePatternEvaluation",
                "alternative_index": index,
                "pattern": alternative,
                "result": result,
                "value": value,
                "selected_case": _match_case_evidence(alternative),
                "selected_branch": condition.get("target"),
            }
        )
        if result:
            break
    return events


def _guard_evaluation_event(
    condition: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    guard = condition.get("guard") or {}
    return {
        "event_type": "GuardEvaluation",
        "expression": guard.get("expression"),
        "result": _expression_value(guard, context),
        "selected_branch": condition.get("target"),
    }


def _comparison_evaluation_event(
    condition: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    comparison = condition["comparison"]
    left = _comparison_operand_value(comparison.get("left"), context)
    right = _comparison_operand_value(comparison.get("right"), context)
    operator = comparison.get("operator")
    return {
        "event_type": "ComparisonEvaluation",
        "expression": _comparison_expression_text(comparison),
        "left_value": left,
        "right_value": right,
        "result": _evaluate_comparison(comparison, context),
        "operator": operator,
    }


def _comparison_expression_text(comparison: dict[str, Any]) -> str:
    return (
        f"{_comparison_operand_text(comparison.get('left'))} "
        f"{comparison.get('operator')} "
        f"{_comparison_operand_text(comparison.get('right'))}"
    )


def _comparison_operand_text(operand: Any) -> str:
    if isinstance(operand, dict):
        if operand.get("node_type") == "IdentifierNode":
            return str(operand.get("name"))
        if operand.get("node_type") in {"IntegerLiteralNode", "FloatLiteralNode"}:
            return str(operand.get("value"))
        if operand.get("node_type") == "BooleanLiteralNode":
            return "true" if operand.get("value") else "false"
    if isinstance(operand, bool):
        return "true" if operand else "false"
    return str(operand)


def _surface_comparison_operator(operator: Any) -> str | None:
    return {
        "Equal": "==",
        "NotEqual": "!=",
        "GreaterThan": ">",
        "GreaterThanOrEqual": ">=",
        "LessThan": "<",
        "LessThanOrEqual": "<=",
    }.get(str(operator))


# ---------------------------------------------------------------------------
# Knowledge engine
# ---------------------------------------------------------------------------

def extract_knowledge(
    ir: dict[str, Any],
    simulation: dict[str, Any],
    *,
    include_all_branches: bool = False,
) -> dict[str, Any]:
    """
    Extract domain knowledge from Reason IR + simulation result.

    Each discovered path from initial_state to any reachable node is
    treated as an IsA / Transition relation and encoded as a knowledge unit.
    """
    transitions = ir.get("transitions", [])
    goal_target = ir.get("goal", {}).get("target", "")
    initial_id = ir.get("initial_state", {}).get("state_id", "")

    # Resolve effective initial state
    all_sources = {t["source"] for t in transitions}
    all_targets = {t["target"] for t in transitions}
    if initial_id not in all_sources and transitions:
        roots = all_sources - all_targets
        initial_id = next(iter(roots)) if roots else transitions[0]["source"]

    # Build adjacency for BFS
    from collections import deque
    adj: dict[str, list[dict[str, Any]]] = {}
    for t in transitions:
        adj.setdefault(t["source"], []).append(t)

    # Find all paths (bounded by depth)
    knowledge_units: list[dict[str, Any]] = []
    queue: deque[tuple[str, list[dict[str, Any]]]] = deque()
    queue.append((initial_id, []))
    visited_states: set[str] = {initial_id}
    selected_branches = set(simulation.get("selected_branches") or [])
    if simulation.get("selected_branch"):
        selected_branches.add(simulation["selected_branch"])
    constrain_to_selected = bool(selected_branches) and not include_all_branches
    seen_knowledge: set[tuple[str, str, str, str]] = set()
    max_knowledge = 16

    while queue and len(knowledge_units) < max_knowledge:
        current, path = queue.popleft()
        for t in adj.get(current, []):
            new_path = path + [t]
            target = t["target"]
            if t.get("relation") == "FunctionReturnTransition":
                if constrain_to_selected and t["transition_id"] not in selected_branches:
                    continue
                if target not in visited_states:
                    visited_states.add(target)
                    queue.append((target, new_path))
                continue

            # Determine relation kind from transition_id naming
            relation = t.get("relation", t["transition_id"])

            # Build path labels for display
            path_labels = (
                [new_path[0]["source"]] + [s["target"] for s in new_path]
            )

            confidence = round(max(0.3, 1.0 - len(new_path) * 0.08), 2)
            evidence = {
                "path": path_labels,
                "transitions": [s["transition_id"] for s in new_path],
            }
            evidence_path = _branch_evidence_path(new_path)
            path_signature = _path_signature_for_path(new_path, evidence_path)
            comparison_evidence = _path_comparison_evidence(new_path)
            match_evidence = _path_match_evidence(new_path)
            enum_match_evidence = _path_enum_match_evidence(new_path)
            optional_match_evidence = _path_optional_match_evidence(new_path)
            struct_match_evidence = _path_struct_match_evidence(new_path)
            guard_evidence = _path_guard_evidence(new_path)
            pattern_evidence = _path_pattern_evidence(new_path)
            or_pattern_evidence = _path_or_pattern_evidence(new_path)
            identity = (new_path[0]["source"], relation, target, path_signature)
            if identity in seen_knowledge:
                continue
            seen_knowledge.add(identity)

            unit = {
                "id": f"K{len(knowledge_units) + 1:03d}",
                "source": new_path[0]["source"],
                "relation": relation,
                "target": target,
                "evidence_path": evidence_path,
                "path_signature": path_signature,
                "branch_id": _branch_id(evidence_path),
                "confidence": confidence,
                "path_length": len(new_path),
                "evidence": evidence,
                "from_simulation": simulation.get("success", False) and target == goal_target,
            }
            if comparison_evidence is not None:
                unit["comparison_evidence"] = comparison_evidence
            if match_evidence is not None:
                unit["match_evidence"] = match_evidence
            if enum_match_evidence is not None:
                unit["enum_match_evidence"] = enum_match_evidence
            if optional_match_evidence is not None:
                unit["optional_match_evidence"] = optional_match_evidence
            if struct_match_evidence is not None:
                unit["struct_match_evidence"] = struct_match_evidence
            if guard_evidence is not None:
                unit["guard_evidence"] = guard_evidence
            if pattern_evidence is not None:
                unit["pattern"] = pattern_evidence["pattern"]
                unit["matched_pattern"] = pattern_evidence["matched_pattern"]
                unit["evaluation_trace"] = pattern_evidence["evaluation_trace"]
                unit["pattern_evidence"] = pattern_evidence
            if or_pattern_evidence is not None:
                unit["or_pattern_evidence"] = or_pattern_evidence
            knowledge_units.append(unit)

            if target not in visited_states and len(new_path) < 8:
                visited_states.add(target)
                queue.append((target, new_path))

    return {
        "schema_version": "knowledge-emergence/0.2",
        "generated_at": "1970-01-01T00:00:00+00:00",
        "knowledge_count": len(knowledge_units),
        "evidence_count": sum(1 for k in knowledge_units if k.get("from_simulation")),
        "knowledge": knowledge_units,
    }


def _branch_evidence_path(path: list[dict[str, Any]]) -> list[str]:
    selected = _selected_return_transition_id(path)
    if selected is None:
        return []
    return _selected_branches_for_transition(selected)


def _selected_return_transition_id(path: list[dict[str, Any]]) -> str | None:
    for transition in path:
        if transition.get("relation") == "FunctionReturnTransition":
            return transition.get("transition_id")
    return None


def _selected_branches_for_transition(transition_id: str | None) -> list[str]:
    if not transition_id:
        return []
    if ".match." not in transition_id:
        return [transition_id]
    branch_id = transition_id.split(".match.", 1)[1]
    if "|" not in branch_id:
        return [transition_id]
    return branch_id.split("|")


def _path_signature_for_path(
    path: list[dict[str, Any]],
    evidence_path: list[str],
) -> str:
    selected = _selected_return_transition_id(path)
    if selected and ".match." in selected and "|" in selected:
        return selected
    return _path_signature(evidence_path)


def _path_signature(evidence_path: list[str]) -> str:
    return "|".join(evidence_path)


def _branch_id(evidence_path: list[str]) -> str | None:
    if not evidence_path:
        return None
    if len(evidence_path) > 1:
        return "|".join(evidence_path)
    branch = evidence_path[-1]
    if ".match." in branch:
        match_id = branch.split(".match.", 1)[1]
        if "." in match_id:
            return match_id
        if match_id in {"some", "none"}:
            return match_id
        return f"case_{match_id}"
    return branch.rsplit(".", 1)[-1]


def _path_comparison_evidence(path: list[dict[str, Any]]) -> dict[str, Any] | None:
    for transition in reversed(path):
        if transition.get("relation") != "FunctionReturnTransition":
            continue
        effect = transition.get("effect") or {}
        context = effect.get("evaluation_context") or {}
        for condition in reversed(effect.get("branch_conditions") or []):
            comparison = condition.get("comparison")
            if comparison is None:
                continue
            return {
                "expression": _comparison_expression_text(comparison),
                "result": _evaluate_comparison(comparison, context),
            }
    return None


def _path_match_evidence(path: list[dict[str, Any]]) -> dict[str, Any] | None:
    for transition in reversed(path):
        if transition.get("relation") != "FunctionReturnTransition":
            continue
        effect = transition.get("effect") or {}
        context = effect.get("evaluation_context") or {}
        for condition in reversed(effect.get("match_conditions") or []):
            return {
                "value": _match_value(condition, context),
                "matched_case": _match_case_evidence(condition.get("pattern")),
            }
    return None


def _path_enum_match_evidence(path: list[dict[str, Any]]) -> dict[str, str] | list[dict[str, str]] | None:
    evidence: list[dict[str, str]] = []
    for transition in reversed(path):
        if transition.get("relation") != "FunctionReturnTransition":
            continue
        effect = transition.get("effect") or {}
        context = effect.get("evaluation_context") or {}
        for condition in effect.get("match_conditions") or []:
            pattern = condition.get("pattern")
            if not _is_enum_pattern(pattern):
                continue
            enum_value = _enum_match_value(_match_value(condition, context))
            if enum_value is not None:
                evidence.append(enum_value)
        if evidence:
            return evidence if len(evidence) > 1 else evidence[0]
    return None


def _path_optional_match_evidence(path: list[dict[str, Any]]) -> dict[str, str] | list[dict[str, str]] | None:
    evidence: list[dict[str, str]] = []
    for transition in reversed(path):
        if transition.get("relation") != "FunctionReturnTransition":
            continue
        effect = transition.get("effect") or {}
        context = effect.get("evaluation_context") or {}
        for condition in effect.get("match_conditions") or []:
            pattern = condition.get("pattern")
            if not _is_optional_pattern(pattern):
                continue
            optional_value = _optional_match_value(_match_value(condition, context))
            if optional_value is not None and isinstance(optional_value.get("kind"), str):
                evidence.append({"kind": optional_value["kind"]})
        if evidence:
            return evidence if len(evidence) > 1 else evidence[0]
    return None


def _path_guard_evidence(path: list[dict[str, Any]]) -> dict[str, Any] | list[dict[str, Any]] | None:
    evidence: list[dict[str, Any]] = []
    for transition in reversed(path):
        if transition.get("relation") != "FunctionReturnTransition":
            continue
        effect = transition.get("effect") or {}
        context = effect.get("evaluation_context") or {}
        for condition in effect.get("match_conditions") or []:
            guard = condition.get("guard")
            if guard is None:
                continue
            evidence.append(
                {
                    "expression": guard.get("expression"),
                    "result": _expression_value(guard, context),
                }
            )
        if evidence:
            return evidence if len(evidence) > 1 else evidence[0]
    return None


def _path_struct_match_evidence(path: list[dict[str, Any]]) -> dict[str, Any] | list[dict[str, Any]] | None:
    evidence: list[dict[str, Any]] = []
    for transition in reversed(path):
        if transition.get("relation") != "FunctionReturnTransition":
            continue
        effect = transition.get("effect") or {}
        for condition in effect.get("match_conditions") or []:
            pattern = condition.get("pattern")
            if not _is_struct_pattern(pattern):
                continue
            evidence.append(
                {
                    "struct": pattern.get("type_name"),
                    "matched_fields": _struct_pattern_matched_fields(pattern),
                }
            )
        if evidence:
            return evidence if len(evidence) > 1 else evidence[0]
    return None


def _path_or_pattern_evidence(path: list[dict[str, Any]]) -> dict[str, Any] | list[dict[str, Any]] | None:
    evidence: list[dict[str, Any]] = []
    for transition in reversed(path):
        if transition.get("relation") != "FunctionReturnTransition":
            continue
        effect = transition.get("effect") or {}
        for condition in effect.get("match_conditions") or []:
            or_pattern = condition.get("or_pattern")
            if not isinstance(or_pattern, dict):
                continue
            alternatives = or_pattern.get("alternatives") or []
            selected_index = or_pattern.get("selected_index")
            selected_pattern = (
                alternatives[selected_index]
                if isinstance(selected_index, int) and 0 <= selected_index < len(alternatives)
                else condition.get("pattern")
            )
            evidence.append(
                {
                    "selected_alternative": selected_index,
                    "selected_case": _match_case_evidence(selected_pattern),
                    "alternative_count": or_pattern.get("alternative_count", len(alternatives)),
                }
            )
        if evidence:
            return evidence if len(evidence) > 1 else evidence[0]
    return None


def _path_pattern_evidence(path: list[dict[str, Any]]) -> dict[str, Any] | None:
    for transition in reversed(path):
        if transition.get("relation") != "FunctionReturnTransition":
            continue
        effect = transition.get("effect") or {}
        for decision in reversed(effect.get("pattern_decisions") or []):
            if not decision.get("matched"):
                continue
            return _pattern_decision_evidence(decision)
    return None


def _pattern_decision_evidence(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "pattern": decision.get("pattern_kind"),
        "matched_pattern": decision.get("matched_pattern"),
        "branch_id": decision.get("branch_id"),
        "matched_fields": decision.get("matched_fields", []),
        "evaluation_trace": decision.get("evaluation_trace", []),
        "confidence": decision.get("confidence"),
    }


def _match_case_evidence(pattern: Any) -> Any:
    if _is_enum_pattern(pattern):
        return _enum_pattern_signature(pattern)
    if _is_optional_pattern(pattern):
        return _optional_pattern_signature(pattern)
    if _is_struct_pattern(pattern):
        return _struct_pattern_signature(pattern)
    if _is_or_pattern(pattern):
        return [
            _match_case_evidence(alternative)
            for alternative in pattern.get("alternatives") or []
        ]
    return pattern


def _enum_pattern_signature(pattern: dict[str, Any]) -> str:
    return f"{pattern.get('enum_name')}.{pattern.get('value_name')}"


def _optional_pattern_signature(pattern: dict[str, Any]) -> str:
    if pattern.get("node_type") == "OptionalSomePatternNode":
        return "some"
    return "none"


def _struct_pattern_signature(pattern: dict[str, Any]) -> str:
    type_name = str(pattern.get("type_name", "Struct"))
    labels: list[str] = []
    for field in pattern.get("fields") or []:
        label = _struct_field_signature(field)
        if label is not None:
            labels.append(label)
    return f"{type_name}.{('_'.join(labels))}" if labels else type_name


def _struct_field_signature(field: Any) -> str | None:
    if not isinstance(field, dict):
        return None
    field_name = str(field.get("field_name") or "")
    pattern = field.get("pattern")
    if not isinstance(pattern, dict):
        return None
    node_type = pattern.get("node_type")
    if node_type == "StructPatternNode":
        return f"{field_name}|{_struct_pattern_signature(pattern)}"
    if node_type == "StructBindingPatternNode":
        return f"bind{pattern.get('binding')}"
    if node_type == "IdentifierPatternNode":
        return f"bind{pattern.get('name')}"
    if node_type == "QualifiedPatternNode":
        return f"{pattern.get('namespace')}.{pattern.get('identifier')}"
    if node_type == "EnumValuePatternNode":
        return f"{pattern.get('enum_name')}.{pattern.get('value_name')}"
    if node_type == "LiteralPatternNode":
        literal = pattern.get("value")
        value = literal.get("value") if isinstance(literal, dict) else literal
        return f"{field_name}{value}"
    if node_type == "WildcardPatternNode":
        return f"{field_name}wildcard"
    return None


def _struct_pattern_matched_fields(pattern: dict[str, Any]) -> list[str]:
    return [
        field["field_name"]
        for field in pattern.get("fields") or []
        if isinstance(field, dict) and isinstance(field.get("field_name"), str)
    ]
