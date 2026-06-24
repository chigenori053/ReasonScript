"""ReasonScript Playground IDE v0.5 — Analysis engine."""

from __future__ import annotations

import datetime
from collections import deque
from typing import Any


def analyze_ir(ir: dict[str, Any], simulation: dict[str, Any], compiler_mode: str = "normal") -> dict[str, Any]:
    """Produce all v0.5 analysis artifacts from a Reason IR + simulation result."""
    return {
        "output": _analyze_output(ir, simulation),
        "dependency_graph": _analyze_dependency_graph(ir),
        "runtime_operations": _analyze_runtime_operations(ir),
        "input_states": _analyze_input_states(ir),
        "calculations": _analyze_calculations(ir),
        "cycle_validation": _analyze_cycles(ir),
        "runtime_trace": _analyze_runtime_trace(ir, simulation),
        "strict_diagnostics": _analyze_strict(ir, compiler_mode),
        "ownership": _analyze_ownership(ir, simulation),
        "type_coverage": _analyze_type_coverage(ir),
        "exhaustiveness": _analyze_exhaustiveness(ir),
        "determinism": _analyze_determinism(ir, simulation),
        "complexity": _analyze_complexity(ir),
        "quality": _analyze_quality(ir, simulation),
    }


def _runtime_call_kind(call: Any) -> str:
    if isinstance(call, dict):
        return call.get("function") or call.get("kind") or call.get("operation", "")
    return str(call)


def _runtime_call_argument(call: Any) -> Any:
    if isinstance(call, dict):
        return call.get("argument") or call.get("target")
    return None


# ---------------------------------------------------------------------------
# Output Panel
# ---------------------------------------------------------------------------

def _analyze_output(ir: dict[str, Any], simulation: dict[str, Any]) -> dict[str, Any]:
    meta = ir.get("metadata", {})
    runtime_ops = meta.get("runtime_operations", [])
    print_ops = [op for op in runtime_ops if op.get("kind") == "print" or op.get("operation") == "print"]

    events: list[dict[str, Any]] = []
    # Generate output events from simulation trace + print ops
    for i, op in enumerate(print_ops):
        target = op.get("target") or op.get("argument") or "?"
        events.append({
            "output_id": str(i + 1),
            "projection": "canonical",
            "rendered_value": target,
            "operation": op,
        })

    # If simulation succeeded and no explicit print ops, synthesize from trace
    if not events and simulation.get("success"):
        trace = simulation.get("trace", [])
        final = simulation.get("final_state", "")
        if final:
            events.append({
                "output_id": "1",
                "projection": "canonical",
                "rendered_value": final,
                "operation": {"kind": "implicit", "target": final},
            })

    return {
        "events": events,
        "event_count": len(events),
        "has_output": len(events) > 0,
    }


# ---------------------------------------------------------------------------
# Dependency Graph
# ---------------------------------------------------------------------------

def _analyze_dependency_graph(ir: dict[str, Any]) -> dict[str, Any]:
    meta = ir.get("metadata", {})
    calc_deps = meta.get("calculation_dependencies", [])
    transitions = ir.get("transitions", [])

    # Build dependency edges
    edges: list[list[str]] = []
    nodes: set[str] = set()

    for dep in calc_deps:
        src = dep.get("from") or dep.get("source")
        tgt = dep.get("to") or dep.get("target")
        if src and tgt:
            edges.append([src, tgt])
            nodes.add(src)
            nodes.add(tgt)

    # Fall back to transitions if no calc deps
    if not edges:
        for t in transitions:
            edges.append([t["source"], t["target"]])
            nodes.add(t["source"])
            nodes.add(t["target"])

    # Topological sort (Kahn's algorithm)
    topo, cycle_nodes = _topo_sort(list(nodes), edges)

    # Compute depth per node
    depth: dict[str, int] = {}
    for node in topo:
        predecessors = [e[0] for e in edges if e[1] == node]
        depth[node] = (max((depth.get(p, 0) for p in predecessors), default=-1) + 1) if predecessors else 0

    return {
        "nodes": sorted(nodes),
        "dependencies": edges,
        "topological_order": topo,
        "depth": depth,
        "has_cycle": len(cycle_nodes) > 0,
        "cycle_nodes": cycle_nodes,
    }


def _topo_sort(nodes: list[str], edges: list[list[str]]) -> tuple[list[str], list[str]]:
    in_degree: dict[str, int] = {n: 0 for n in nodes}
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for src, tgt in edges:
        if tgt in in_degree:
            in_degree[tgt] += 1
        if src in adj:
            adj[src].append(tgt)
    queue = deque([n for n in nodes if in_degree.get(n, 0) == 0])
    order: list[str] = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for m in adj.get(n, []):
            in_degree[m] -= 1
            if in_degree[m] == 0:
                queue.append(m)
    remaining = [n for n in nodes if n not in order]
    return order, remaining


# ---------------------------------------------------------------------------
# Runtime Operations
# ---------------------------------------------------------------------------

def _analyze_runtime_operations(ir: dict[str, Any]) -> dict[str, Any]:
    meta = ir.get("metadata", {})
    ops = meta.get("runtime_operations", [])
    runtime_calls = meta.get("runtime_calls", [])

    all_ops = list(ops) + [
        (
            {"kind": c.get("function") or c.get("kind", "unknown"), "argument": c.get("argument")}
            if isinstance(c, dict)
            else {"kind": str(c), "argument": None}
        )
        for c in runtime_calls
        if (c.get("function") if isinstance(c, dict) else str(c)) not in {o.get("kind") for o in ops}
    ]

    by_kind: dict[str, list[dict[str, Any]]] = {}
    for op in all_ops:
        kind = op.get("kind") or op.get("operation") or "unknown"
        by_kind.setdefault(kind, []).append(op)

    return {
        "operations": all_ops,
        "count": len(all_ops),
        "by_kind": by_kind,
        "kinds": sorted(by_kind.keys()),
    }


# ---------------------------------------------------------------------------
# InputState
# ---------------------------------------------------------------------------

def _analyze_input_states(ir: dict[str, Any]) -> dict[str, Any]:
    meta = ir.get("metadata", {})
    runtime_calls = meta.get("runtime_calls", [])
    runtime_ops = meta.get("runtime_operations", [])

    input_states: list[dict[str, Any]] = []
    idx = 1
    for call in runtime_calls:
        if _runtime_call_kind(call) == "input":
            input_states.append({
                "state_id": f"Input{idx}",
                "state_type": "Input",
                "argument": _runtime_call_argument(call),
                "value": call.get("value") if isinstance(call, dict) else None,
            })
            idx += 1
    for op in runtime_ops:
        if op.get("kind") == "input" or op.get("operation") == "input":
            input_states.append({
                "state_id": f"Input{idx}",
                "state_type": "Input",
                "argument": op.get("argument") or op.get("target"),
                "value": op.get("value"),
            })
            idx += 1

    return {
        "input_states": input_states,
        "count": len(input_states),
    }


# ---------------------------------------------------------------------------
# Calculation Inspector
# ---------------------------------------------------------------------------

def _analyze_calculations(ir: dict[str, Any]) -> dict[str, Any]:
    meta = ir.get("metadata", {})
    calc_order = meta.get("calculation_order", [])
    calc_deps = meta.get("calculation_dependencies", [])
    transitions = ir.get("transitions", [])

    calculations: list[dict[str, Any]] = []
    for name in calc_order:
        deps = [d.get("from") or d.get("source") for d in calc_deps if (d.get("to") or d.get("target")) == name]
        relevant_transitions = [t for t in transitions if t.get("source") in deps or t.get("target") == name]
        calculations.append({
            "name": name,
            "inputs": [f"{d}.state.result" for d in deps],
            "dependencies": deps,
            "transitions": [t["transition_id"] for t in relevant_transitions],
            "output_state": f"{name}.state.result",
        })

    # If no explicit calc order, show transitions as pseudo-calculations
    if not calculations:
        for t in transitions:
            calculations.append({
                "name": t["transition_id"],
                "inputs": [t["source"]],
                "dependencies": [t["source"]],
                "transitions": [t["transition_id"]],
                "output_state": t["target"],
            })

    return {
        "calculations": calculations,
        "count": len(calculations),
    }


# ---------------------------------------------------------------------------
# Cycle Validation
# ---------------------------------------------------------------------------

def _analyze_cycles(ir: dict[str, Any]) -> dict[str, Any]:
    graph_data = _analyze_dependency_graph(ir)
    has_cycle = graph_data["has_cycle"]
    cycle_nodes = graph_data["cycle_nodes"]

    errors: list[dict[str, Any]] = []
    if has_cycle:
        errors.append({
            "code": "CAL-030",
            "message": "Dependency Cycle Detected",
            "nodes": cycle_nodes,
        })

    return {
        "has_cycle": has_cycle,
        "cycle_nodes": cycle_nodes,
        "errors": errors,
        "ok": not has_cycle,
    }


# ---------------------------------------------------------------------------
# Runtime Trace
# ---------------------------------------------------------------------------

def _analyze_runtime_trace(ir: dict[str, Any], simulation: dict[str, Any]) -> dict[str, Any]:
    trace = simulation.get("trace", [])
    transitions = {t["transition_id"]: t for t in ir.get("transitions", [])}
    meta = ir.get("metadata", {})
    runtime_ops = meta.get("runtime_operations", [])

    enriched_trace: list[dict[str, Any]] = []
    for step in trace:
        entry: dict[str, Any] = {
            "step": step.get("step", 0),
            "kind": step.get("event", "unknown"),
            "state": step.get("state"),
        }
        if step.get("transition"):
            tid = step["transition"]
            t = transitions.get(tid, {})
            entry["transition"] = {
                "id": tid,
                "source": t.get("source"),
                "target": t.get("target"),
                "relation": t.get("relation"),
            }
            entry["kind"] = "Transition"
        elif step.get("event") == "start":
            entry["kind"] = "InputState"
        enriched_trace.append(entry)

    # Add output events
    output_data = _analyze_output(ir, simulation)
    for event in output_data["events"]:
        enriched_trace.append({
            "step": len(enriched_trace),
            "kind": "OutputEvent",
            "rendered_value": event["rendered_value"],
        })

    return {
        "trace": enriched_trace,
        "step_count": len(enriched_trace),
        "success": simulation.get("success", False),
        "final_state": simulation.get("final_state"),
    }


# ---------------------------------------------------------------------------
# Strict Compiler Diagnostics
# ---------------------------------------------------------------------------

def _analyze_strict(ir: dict[str, Any], compiler_mode: str) -> dict[str, Any]:
    if compiler_mode == "normal":
        return {"mode": "normal", "diagnostics": [], "count": 0}

    meta = ir.get("metadata", {})
    transitions = ir.get("transitions", [])
    reasoning = meta.get("reasoning_declarations", {})

    diagnostics: list[dict[str, Any]] = []

    # Unused declarations check
    declared_goals = {g["name"] for g in reasoning.get("goals", [])}
    goal_target = ir.get("goal", {}).get("target", "")
    for g in declared_goals:
        if g != goal_target:
            diagnostics.append({"code": "STRICT-001", "kind": "unused_goal", "name": g, "message": f"Goal '{g}' is declared but not targeted"})

    # Dead transitions (unreachable states)
    reachable = _reachable_states(ir)
    all_transition_sources = {t["source"] for t in transitions}
    all_transition_targets = {t["target"] for t in transitions}
    all_states = all_transition_sources | all_transition_targets
    unreachable = all_states - reachable
    for s in sorted(unreachable):
        diagnostics.append({"code": "STRICT-002", "kind": "dead_transition", "state": s, "message": f"State '{s}' is unreachable from initial state"})

    if compiler_mode == "rust_compatible":
        # Exhaustiveness placeholder
        if not reasoning.get("goals"):
            diagnostics.append({"code": "RUST-001", "kind": "missing_goal", "message": "No goal declared — exhaustiveness cannot be verified"})

    return {
        "mode": compiler_mode,
        "diagnostics": diagnostics,
        "count": len(diagnostics),
    }


def _reachable_states(ir: dict[str, Any]) -> set[str]:
    transitions = ir.get("transitions", [])
    initial_id = ir.get("initial_state", {}).get("state_id", "")
    all_sources = {t["source"] for t in transitions}
    all_targets = {t["target"] for t in transitions}
    if initial_id not in all_sources and transitions:
        roots = all_sources - all_targets
        initial_id = next(iter(roots)) if roots else (transitions[0]["source"] if transitions else "")
    adj: dict[str, list[str]] = {}
    for t in transitions:
        adj.setdefault(t["source"], []).append(t["target"])
    visited: set[str] = set()
    queue = deque([initial_id])
    while queue:
        n = queue.popleft()
        if n in visited:
            continue
        visited.add(n)
        for m in adj.get(n, []):
            queue.append(m)
    return visited


# ---------------------------------------------------------------------------
# Ownership Analysis
# ---------------------------------------------------------------------------

def _analyze_ownership(ir: dict[str, Any], simulation: dict[str, Any]) -> dict[str, Any]:
    transitions = ir.get("transitions", [])
    trace = simulation.get("trace", [])

    producers: dict[str, str] = {}
    consumers: dict[str, str] = {}
    lifetimes: dict[str, dict[str, Any]] = {}

    for t in transitions:
        src, tgt = t["source"], t["target"]
        producers[tgt] = t["transition_id"]
        consumers[src] = t["transition_id"]

    for step in trace:
        state = step.get("state")
        if state:
            if state not in lifetimes:
                lifetimes[state] = {"created_at": step.get("step"), "consumed_at": None}
            elif step.get("event") == "transition":
                lifetimes[state]["consumed_at"] = step.get("step")

    ownership_entries: list[dict[str, Any]] = []
    all_states = sorted({t["source"] for t in transitions} | {t["target"] for t in transitions})
    for state in all_states:
        ownership_entries.append({
            "state": state,
            "producer": producers.get(state),
            "consumer": consumers.get(state),
            "lifetime": lifetimes.get(state),
            "borrow_candidate": producers.get(state) is not None and consumers.get(state) is not None,
            "move_candidate": consumers.get(state) is not None and producers.get(state) is None,
            "clone_candidate": False,
        })

    return {
        "entries": ownership_entries,
        "count": len(ownership_entries),
    }


# ---------------------------------------------------------------------------
# Type Coverage
# ---------------------------------------------------------------------------

def _analyze_type_coverage(ir: dict[str, Any]) -> dict[str, Any]:
    meta = ir.get("metadata", {})
    reasoning_types = meta.get("reasoning_types", [])
    reasoning = meta.get("reasoning_declarations", {})

    declared: list[dict[str, Any]] = []
    inferred: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []

    for rt in reasoning_types:
        if isinstance(rt, dict):
            name = rt.get("name") or rt.get("id", "?")
            kind = rt.get("kind") or rt.get("type", "Unknown")
        else:
            name = str(rt)
            kind = str(rt)
        entry = {"name": name, "type": kind}
        if kind in {"InputState", "OutputState", "Calculation", "GoalState"}:
            declared.append(entry)
        elif kind == "Unknown":
            unknown.append(entry)
        else:
            inferred.append(entry)

    # Add transitions as inferred types if no reasoning_types
    if not declared and not inferred and not unknown:
        transitions = ir.get("transitions", [])
        for t in transitions:
            inferred.append({"name": t["source"], "type": "StateNode"})
            inferred.append({"name": t["target"], "type": "StateNode"})
        # deduplicate
        seen: set[str] = set()
        deduped = []
        for e in inferred:
            if e["name"] not in seen:
                seen.add(e["name"])
                deduped.append(e)
        inferred = deduped

    total = len(declared) + len(inferred) + len(unknown)
    coverage = round((len(declared) + len(inferred)) / total * 100, 1) if total > 0 else 100.0

    return {
        "declared": declared,
        "inferred": inferred,
        "unknown": unknown,
        "total": total,
        "coverage_pct": coverage,
        "has_unknowns": len(unknown) > 0,
    }


# ---------------------------------------------------------------------------
# Exhaustiveness
# ---------------------------------------------------------------------------

def _analyze_exhaustiveness(ir: dict[str, Any]) -> dict[str, Any]:
    meta = ir.get("metadata", {})
    reasoning = meta.get("reasoning_declarations", {})
    transitions = ir.get("transitions", [])

    # Collect all declared concepts/states
    all_states = sorted({t["source"] for t in transitions} | {t["target"] for t in transitions})
    goal_target = ir.get("goal", {}).get("target", "")

    # "handled" = states that have outgoing transitions or are the goal
    has_outgoing = {t["source"] for t in transitions}
    handled = sorted(s for s in all_states if s in has_outgoing or s == goal_target)
    missing = sorted(s for s in all_states if s not in handled)

    return {
        "all_states": all_states,
        "handled": handled,
        "missing": missing,
        "is_exhaustive": len(missing) == 0,
        "coverage_pct": round(len(handled) / len(all_states) * 100, 1) if all_states else 100.0,
    }


# ---------------------------------------------------------------------------
# Determinism Inspector
# ---------------------------------------------------------------------------

def _analyze_determinism(ir: dict[str, Any], simulation: dict[str, Any]) -> dict[str, Any]:
    meta = ir.get("metadata", {})
    runtime_ops = meta.get("runtime_operations", [])
    runtime_calls = meta.get("runtime_calls", [])

    input_boundaries: list[dict[str, Any]] = []
    non_deterministic: list[dict[str, Any]] = []

    for op in runtime_ops + runtime_calls:
        kind = _runtime_call_kind(op)
        if kind == "input":
            input_boundaries.append({"kind": "input", "argument": _runtime_call_argument(op)})
            non_deterministic.append({"source": "input()", "reason": "External user input"})
        elif kind in {"search", "predict", "simulate", "plan"}:
            non_deterministic.append({"source": f"{kind}()", "reason": "External system dependency"})

    # All transitions are deterministic after boundary
    det_transitions = ir.get("transitions", [])
    deterministic_after_boundary = len(det_transitions) > 0

    projection_stable = simulation.get("success", False)

    return {
        "deterministic_transitions": [t["transition_id"] for t in det_transitions],
        "input_boundaries": input_boundaries,
        "non_deterministic_sources": non_deterministic,
        "deterministic_after_boundary": deterministic_after_boundary,
        "projection_stable": projection_stable,
        "knowledge_reproducible": True,
        "overall_deterministic": len(non_deterministic) == 0,
    }


# ---------------------------------------------------------------------------
# Complexity Report
# ---------------------------------------------------------------------------

def _analyze_complexity(ir: dict[str, Any]) -> dict[str, Any]:
    meta = ir.get("metadata", {})
    transitions = ir.get("transitions", [])
    reasoning = meta.get("reasoning_declarations", {})
    calc_deps = meta.get("calculation_dependencies", [])
    runtime_ops = meta.get("runtime_operations", [])

    graph = _analyze_dependency_graph(ir)
    depth_values = list(graph.get("depth", {}).values())
    max_depth = max(depth_values, default=0)

    return {
        "states": len({t["source"] for t in transitions} | {t["target"] for t in transitions}),
        "transitions": len(transitions),
        "dependency_count": len(calc_deps) if calc_deps else len(transitions),
        "dependency_depth": max_depth,
        "knowledge_units": 0,
        "simulation_depth": len(ir.get("transitions", [])),
        "runtime_operations": len(runtime_ops) + len(meta.get("runtime_calls", [])),
        "goals": len(reasoning.get("goals", [])),
        "constraints": len(ir.get("constraints", [])),
    }


# ---------------------------------------------------------------------------
# Rust Compatibility Dashboard
# ---------------------------------------------------------------------------

def _analyze_quality(ir: dict[str, Any], simulation: dict[str, Any]) -> dict[str, Any]:
    meta = ir.get("metadata", {})
    transitions = ir.get("transitions", [])
    constraints = ir.get("constraints", [])
    reasoning = meta.get("reasoning_declarations", {})
    runtime_ops = meta.get("runtime_operations", [])
    reasoning_types = meta.get("reasoning_types", [])

    # Namespace Safety: module declared?
    module_name = meta.get("module") or meta.get("namespace")
    namespace_safety = 100 if module_name else 60

    # Type Safety: based on type coverage
    type_data = _analyze_type_coverage(ir)
    type_safety = int(type_data["coverage_pct"])

    # Dependency Safety: no cycles
    cycle_data = _analyze_cycles(ir)
    dependency_safety = 0 if cycle_data["has_cycle"] else 100

    # Ownership Readiness: rough estimate based on transition structure
    ownership_data = _analyze_ownership(ir, simulation)
    owned = sum(1 for e in ownership_data["entries"] if e.get("producer") or e.get("consumer"))
    total_states = len(ownership_data["entries"]) or 1
    ownership_readiness = int(owned / total_states * 40)  # cap at 40% (future feature)

    # Exhaustiveness
    exh_data = _analyze_exhaustiveness(ir)
    exhaustiveness = int(exh_data["coverage_pct"])

    # Determinism
    det_data = _analyze_determinism(ir, simulation)
    determinism = 100 if det_data["overall_deterministic"] else max(50, 100 - len(det_data["non_deterministic_sources"]) * 20)

    # Runtime Safety: based on runtime ops being well-formed
    ops_count = len(runtime_ops) + len(meta.get("runtime_calls", []))
    runtime_safety = 80 if ops_count == 0 else min(95, 60 + (20 if simulation.get("success") else 0))

    # Compiler Consistency: success + no cycle
    compiler_consistency = 100 if (simulation.get("success") and not cycle_data["has_cycle"]) else 70

    metrics = [
        {"name": "Namespace Safety", "pct": namespace_safety},
        {"name": "Type Safety", "pct": type_safety},
        {"name": "Dependency Safety", "pct": dependency_safety},
        {"name": "Ownership Readiness", "pct": ownership_readiness},
        {"name": "Exhaustiveness", "pct": exhaustiveness},
        {"name": "Determinism", "pct": determinism},
        {"name": "Runtime Safety", "pct": runtime_safety},
        {"name": "Compiler Consistency", "pct": compiler_consistency},
    ]

    overall = int(sum(m["pct"] for m in metrics) / len(metrics))

    return {
        "schema_version": "rust-compat/0.1",
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "compiler_version": "ReasonScript v0.1 Alpha",
        "metrics": metrics,
        "overall_pct": overall,
    }
