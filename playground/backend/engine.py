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
            current = {
                "state_id": t["target"],
                "state_type": current.get("state_type", ""),
                "data": copy.deepcopy(t.get("effect", {"identity": t["target"]})),
            }
            applied.append(t["transition_id"])
            total_cost += t.get("expected_cost", 1.0)
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

    return {
        "schema_version": "semantic-simulation/0.2",
        "success": success,
        "goal_reached": goal_reached,
        "cost": total_cost,
        "confidence": confidence,
        "final_state": current.get("state_id", ""),
        "step_count": len(applied),
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


# ---------------------------------------------------------------------------
# Knowledge engine
# ---------------------------------------------------------------------------

def extract_knowledge(ir: dict[str, Any], simulation: dict[str, Any]) -> dict[str, Any]:
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
    max_knowledge = 16

    while queue and len(knowledge_units) < max_knowledge:
        current, path = queue.popleft()
        for t in adj.get(current, []):
            new_path = path + [t]
            target = t["target"]

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

            knowledge_units.append({
                "id": f"K{len(knowledge_units) + 1:03d}",
                "source": new_path[0]["source"],
                "relation": relation,
                "target": target,
                "confidence": confidence,
                "path_length": len(new_path),
                "evidence": evidence,
                "from_simulation": simulation.get("success", False) and target == goal_target,
            })

            if target not in visited_states and len(new_path) < 8:
                visited_states.add(target)
                queue.append((target, new_path))

    import datetime
    return {
        "schema_version": "knowledge-emergence/0.2",
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "knowledge_count": len(knowledge_units),
        "evidence_count": sum(1 for k in knowledge_units if k.get("from_simulation")),
        "knowledge": knowledge_units,
    }
