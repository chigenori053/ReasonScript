"""Playground language-surface integration audit.

The audit is intentionally executable: every row in the feature matrix is backed
by a minimal source sample that is parsed, projected, lowered, analyzed, and
checked for exportable artifacts through the same Playground backend pipeline.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from frontend.ast import to_json_value as semantic_to_json_value
from frontend.language_surface.integration import compile_program, project_program
from frontend.language_surface.nodes import to_json_value as surface_to_json_value
from frontend.language_surface.parser import parse
from playground.backend.analyzer import analyze_ir
from playground.backend.engine import build_execution_plan, extract_knowledge, simulate


FEATURE_SAMPLES: dict[str, dict[str, Any]] = {
    "module": {
        "source": "module Basic {\n}\n",
        "surface_nodes": ["ModuleNode"],
        "semantic_nodes": ["ModuleNode"],
        "ir_markers": ["BasicStart"],
    },
    "calculation": {
        "source": "module Basic {\n  calculation Value {\n    result = 42\n  }\n}\n",
        "surface_nodes": ["CalculationNode", "ResultStatementNode"],
        "ir_markers": ["ResultTransition"],
    },
    "dependency graph": {
        "source": "module Basic {\n  calculation A {\n    result = 10\n  }\n  calculation B {\n    result = A * 2\n  }\n}\n",
        "surface_nodes": ["CalculationNode", "BinaryExpressionNode"],
        "ir_markers": ["calculation_dependencies"],
        "analysis_paths": ["dependency_graph.dependencies"],
    },
    "execution plan": {
        "source": "module Basic {\n  object Start\n  object End\n  transition Move {\n    Start -> End\n  }\n  goal ReachEnd\n}\n",
        "surface_nodes": ["TransitionNode", "GoalNode"],
        "ir_markers": ["Move"],
        "pipeline_paths": ["execution_plan.selected_steps"],
    },
    "simulation": {
        "source": "module Basic {\n  object Start\n  object End\n  transition Move {\n    Start -> End\n  }\n  goal ReachEnd\n}\n",
        "surface_nodes": ["TransitionNode"],
        "pipeline_paths": ["simulation.trace"],
    },
    "knowledge": {
        "source": "module Basic {\n  object Start\n  object End\n  transition Move {\n    Start -> End\n  }\n  goal ReachEnd\n}\n",
        "surface_nodes": ["TransitionNode"],
        "pipeline_paths": ["knowledge.knowledge"],
    },
    "fn": {
        "source": "module Basic {\n  fn Value() -> int {\n    return 42\n  }\n}\n",
        "surface_nodes": ["FunctionDeclarationNode"],
        "ir_markers": ["function_declarations"],
    },
    "return": {
        "source": "module Basic {\n  fn Value() -> int {\n    return 42\n  }\n}\n",
        "surface_nodes": ["ReturnStatementNode"],
        "ir_markers": ["ReturnStatementNode"],
    },
    "bool": {
        "source": "module Basic {\n  calculation Value {\n    let ok: bool = true\n    result = ok\n  }\n}\n",
        "surface_nodes": ["BooleanLiteralNode", "PrimitiveTypeNode"],
        "ir_markers": ["ExpressionTransition"],
    },
    "if": {
        "source": "module Basic {\n  calculation Value {\n    if true {\n      let x = 1\n    } else {\n      let y = 2\n    }\n    result = 42\n  }\n}\n",
        "surface_nodes": ["IfStatementNode", "ElseStatementNode"],
        "ir_markers": ["DecisionTransition"],
    },
    "elif": {
        "source": "module Basic {\n  calculation Value {\n    if false {\n      let x = 1\n    } elif true {\n      let y = 2\n    } else {\n      let z = 3\n    }\n    result = 42\n  }\n}\n",
        "surface_nodes": ["ElseIfStatementNode"],
        "ir_markers": ["DecisionTransition"],
    },
    "match": {
        "source": "module Basic {\n  enum Color {\n    Red\n    Blue\n  }\n  calculation Value {\n    let c: Color = Color.Red\n    match c {\n      Color.Red => let x = 1\n      Color.Blue => let y = 2\n    }\n    result = 1\n  }\n}\n",
        "surface_nodes": ["MatchStatementNode", "MatchArmNode"],
        "ir_markers": ["DecisionTransition"],
    },
    "for": {
        "source": "module Basic {\n  calculation Value {\n    for item in [1, 2] {\n      continue\n    }\n    result = 2\n  }\n}\n",
        "surface_nodes": ["ForStatementNode"],
        "ir_markers": ["ForTransition"],
    },
    "while": {
        "source": "module Basic {\n  calculation Value {\n    let x = 0\n    while x < 1 {\n      break\n    }\n    result = x\n  }\n}\n",
        "surface_nodes": ["WhileStatementNode"],
        "ir_markers": ["WhileTransition"],
    },
    "loop": {
        "source": "module Basic {\n  calculation Value {\n    loop {\n      break\n    }\n    result = 1\n  }\n}\n",
        "surface_nodes": ["LoopStatementNode"],
        "ir_markers": ["LoopTransition"],
    },
    "break": {
        "source": "module Basic {\n  calculation Value {\n    loop {\n      break\n    }\n    result = 1\n  }\n}\n",
        "surface_nodes": ["BreakStatementNode"],
        "ir_markers": ["BreakStatementNode"],
    },
    "continue": {
        "source": "module Basic {\n  calculation Value {\n    for item in [1, 2] {\n      continue\n    }\n    result = 2\n  }\n}\n",
        "surface_nodes": ["ContinueStatementNode"],
        "ir_markers": ["ContinueStatementNode"],
    },
    "struct": {
        "source": "module Basic {\n  struct Point {\n    x: int\n  }\n  calculation Value {\n    let p: Point = Point {\n      x: 1\n    }\n    result = p.x\n  }\n}\n",
        "surface_nodes": ["StructDeclarationNode", "StructLiteralExpressionNode"],
        "ir_markers": ["composite_declarations", "StructLiteralTransition"],
    },
    "enum": {
        "source": "module Basic {\n  enum Color {\n    Red\n    Blue\n  }\n  calculation Value {\n    let c: Color = Color.Red\n    result = 1\n  }\n}\n",
        "surface_nodes": ["EnumDeclarationNode", "EnumValueNode"],
        "ir_markers": ["composite_declarations"],
    },
    "array": {
        "source": "module Basic {\n  calculation Value {\n    let xs: [int] = [1, 2]\n    result = xs[0]\n  }\n}\n",
        "surface_nodes": ["ArrayTypeNode", "ArrayLiteralNode", "IndexAccessNode"],
        "ir_markers": ["ArrayTransition"],
    },
    "tuple": {
        "source": "module Basic {\n  calculation Value {\n    let pair: (int, int) = (1, 2)\n    result = pair.0\n  }\n}\n",
        "surface_nodes": ["TupleTypeNode", "TupleLiteralNode"],
        "ir_markers": ["TupleTransition"],
    },
    "map": {
        "source": "module Basic {\n  calculation Value {\n    let xs: map<string, int> = map {\n      \"a\": 1\n    }\n    result = xs[\"a\"]\n  }\n}\n",
        "surface_nodes": ["MapTypeNode", "MapLiteralNode"],
        "ir_markers": ["MapTransition"],
    },
    "set": {
        "source": "module Basic {\n  calculation Value {\n    let xs: set<int> = set {\n      1\n    }\n    result = 1\n  }\n}\n",
        "surface_nodes": ["SetTypeNode", "SetLiteralNode"],
        "ir_markers": ["SetTransition"],
    },
    "optional": {
        "source": "module Basic {\n  calculation Value -> optional<int> {\n    let x: optional<int> = some(1)\n    result = x\n  }\n}\n",
        "surface_nodes": ["OptionalTypeNode", "SomeExpressionNode"],
        "ir_markers": ["SomeTransition"],
    },
    "package": {
        "source": "package Demo\nmodule Basic {\n  calculation Value {\n    result = 1\n  }\n}\n",
        "surface_nodes": ["PackageDeclarationNode"],
        "ir_markers": ["package"],
    },
    "import": {
        "source": "module Lib {\n  export calculation Value {\n    result = 1\n  }\n}\nmodule Basic {\n  import Lib.Value\n  calculation Use {\n    result = 2\n  }\n}\n",
        "surface_nodes": ["ImportNode", "ImportResolutionNode"],
        "ir_markers": ["import_resolution"],
    },
    "export": {
        "source": "module Basic {\n  export calculation Value {\n    result = 1\n  }\n}\n",
        "surface_nodes": ["CalculationNode"],
        "ir_markers": ["exports", "Value"],
    },
    "runtime.search": {
        "source": "module Basic {\n  calculation Value {\n    let x = runtime.search(\"goal\")\n    result = x\n  }\n}\n",
        "surface_nodes": ["RuntimeCallExpressionNode"],
        "ir_markers": ["RuntimeSearchNode"],
        "analysis_paths": ["runtime_operations.operations"],
    },
    "runtime.simulate": {
        "source": "module Basic {\n  calculation Value {\n    let x = runtime.simulate(\"plan\")\n    result = x\n  }\n}\n",
        "surface_nodes": ["RuntimeCallExpressionNode"],
        "ir_markers": ["RuntimeSimulateNode"],
        "analysis_paths": ["runtime_operations.operations"],
    },
    "runtime.predict": {
        "source": "module Basic {\n  calculation Value {\n    let x = runtime.predict(\"state\")\n    result = x\n  }\n}\n",
        "surface_nodes": ["RuntimeCallExpressionNode"],
        "ir_markers": ["RuntimePredictNode"],
        "analysis_paths": ["runtime_operations.operations"],
    },
    "runtime.plan": {
        "source": "module Basic {\n  calculation Value {\n    let x = runtime.plan(\"goal\")\n    result = x\n  }\n}\n",
        "surface_nodes": ["RuntimeCallExpressionNode"],
        "ir_markers": ["RuntimePlanNode"],
        "analysis_paths": ["runtime_operations.operations"],
    },
}


def run_language_audit() -> dict[str, Any]:
    rows = [_audit_feature(name, spec) for name, spec in FEATURE_SAMPLES.items()]
    summary = {
        "total": len(rows),
        "connected": sum(1 for row in rows if row["status"] == "CONNECTED"),
        "partial": sum(1 for row in rows if row["status"] == "PARTIAL"),
        "missing": sum(1 for row in rows if row["status"] == "MISSING"),
        "broken": sum(1 for row in rows if row["status"] == "BROKEN"),
    }
    summary["connected_pct"] = round(summary["connected"] * 100 / summary["total"], 2)
    return {
        "schema_version": "playground-feature-matrix/1.0",
        "specification_id": "playground-integration/1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": summary,
        "features": rows,
    }


def write_language_audit_reports(root: Path) -> dict[str, str]:
    matrix = run_language_audit()
    missing = [row for row in matrix["features"] if row["status"] != "CONNECTED"]
    files = {
        "matrix": root / "playground_feature_matrix.json",
        "audit": root / "playground_language_audit.md",
        "missing": root / "playground_missing_features.md",
        "integration": root / "playground_integration_report.md",
    }
    files["matrix"].write_text(json.dumps(matrix, indent=2, ensure_ascii=False), encoding="utf-8")
    files["audit"].write_text(_audit_markdown(matrix), encoding="utf-8")
    files["missing"].write_text(_missing_markdown(matrix, missing), encoding="utf-8")
    files["integration"].write_text(_integration_markdown(matrix, missing), encoding="utf-8")
    return {key: str(path) for key, path in files.items()}


def _audit_feature(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    try:
        program = parse(spec["source"])
        ast = surface_to_json_value(program)
        checks.append(_check("parse", True))
        checks.extend(_node_checks("ast", ast, spec.get("surface_nodes", [])))
    except Exception as error:
        return _row(name, "MISSING", checks + [_check("parse", False, str(error))], spec)

    try:
        semantic_modules = project_program(program)
        semantic_ast = [semantic_to_json_value(module) for module in semantic_modules]
        checks.append(_check("semantic", True))
        checks.extend(_node_checks("semantic_ast", semantic_ast, spec.get("semantic_nodes", [])))
    except Exception as error:
        return _row(name, "BROKEN", checks + [_check("semantic", False, str(error))], spec)

    try:
        reason_irs = list(compile_program(program))
        checks.append(_check("reason_ir", True))
        for marker in spec.get("ir_markers", []):
            checks.append(_check(f"reason_ir contains {marker}", _contains(reason_irs, marker)))
    except Exception as error:
        return _row(name, "BROKEN", checks + [_check("reason_ir", False, str(error))], spec)

    try:
        plans = [build_execution_plan(ir) for ir in reason_irs]
        sims = [simulate(ir) for ir in reason_irs]
        knowledges = [extract_knowledge(ir, sim) for ir, sim in zip(reason_irs, sims)]
        analyses = [analyze_ir(ir, sim) for ir, sim in zip(reason_irs, sims)]
        artifacts = {
            "ast": ast,
            "semantic_ast": semantic_ast[0] if len(semantic_ast) == 1 else {"modules": semantic_ast},
            "reason_ir": reason_irs[0] if len(reason_irs) == 1 else {"modules": reason_irs},
            "execution_plan": plans[0] if len(plans) == 1 else {"modules": plans},
            "simulation": sims[0] if len(sims) == 1 else {"modules": sims},
            "knowledge": knowledges[0] if len(knowledges) == 1 else {"modules": knowledges},
            "analysis": analyses[0] if len(analyses) == 1 else {"modules": analyses},
        }
        checks.extend(
            [
                _check("execution_plan", all(plan is not None for plan in plans)),
                _check("simulation", all(sim is not None for sim in sims)),
                _check("knowledge", all(knowledge is not None for knowledge in knowledges)),
                _check("exportable_artifacts", all(artifacts.get(key) is not None for key in ("ast", "semantic_ast", "reason_ir", "execution_plan", "simulation", "knowledge"))),
            ]
        )
        for path in spec.get("pipeline_paths", []):
            checks.append(_check(f"pipeline path {path}", _path_has_value(artifacts, path)))
        for path in spec.get("analysis_paths", []):
            checks.append(_check(f"analysis path {path}", _path_has_value(artifacts["analysis"], path)))
    except Exception as error:
        return _row(name, "BROKEN", checks + [_check("pipeline", False, str(error))], spec)

    status = "CONNECTED" if all(check["ok"] for check in checks) else "PARTIAL"
    return _row(name, status, checks, spec)


def _row(name: str, status: str, checks: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "feature": name,
        "compiler": True,
        "playground": status == "CONNECTED",
        "status": status,
        "checks": checks,
        "source": spec["source"],
    }


def _check(name: str, ok: bool, detail: str | None = None) -> dict[str, Any]:
    result = {"name": name, "ok": bool(ok)}
    if detail:
        result["detail"] = detail
    return result


def _node_checks(label: str, value: Any, expected: list[str]) -> list[dict[str, Any]]:
    return [_check(f"{label} contains {node}", _contains(value, node)) for node in expected]


def _contains(value: Any, expected: str) -> bool:
    if isinstance(value, str):
        return expected in value
    if isinstance(value, dict):
        return any(_contains(k, expected) or _contains(v, expected) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains(item, expected) for item in value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _contains(dataclasses.asdict(value), expected)
    return str(value) == expected


def _path_has_value(value: Any, path: str) -> bool:
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return False
    if current is None:
        return False
    if isinstance(current, (list, tuple, dict)):
        return len(current) > 0
    return True


def _audit_markdown(matrix: dict[str, Any]) -> str:
    lines = [
        "# Playground Language Audit",
        "",
        f"Specification ID: {matrix['specification_id']}",
        f"Generated At: {matrix['generated_at']}",
        "",
        "| Feature | Compiler | Playground | Status |",
        "|---|---:|---:|---|",
    ]
    for row in matrix["features"]:
        lines.append(
            f"| {row['feature']} | {'yes' if row['compiler'] else 'no'} | "
            f"{'yes' if row['playground'] else 'no'} | {row['status']} |"
        )
    return "\n".join(lines) + "\n"


def _missing_markdown(matrix: dict[str, Any], missing: list[dict[str, Any]]) -> str:
    lines = ["# Playground Missing Features", ""]
    if not missing:
        lines.append("No MISSING, PARTIAL, or BROKEN feature integrations remain.")
        return "\n".join(lines) + "\n"
    for row in missing:
        failed = [check for check in row["checks"] if not check["ok"]]
        lines.append(f"## {row['feature']} - {row['status']}")
        for check in failed:
            detail = f": {check['detail']}" if check.get("detail") else ""
            lines.append(f"- {check['name']}{detail}")
        lines.append("")
    return "\n".join(lines)


def _integration_markdown(matrix: dict[str, Any], missing: list[dict[str, Any]]) -> str:
    summary = matrix["summary"]
    complete = not missing
    return "\n".join(
        [
            "# Playground Integration Report",
            "",
            f"Status: {'COMPLETE' if complete else 'INCOMPLETE'}",
            "",
            f"- CONNECTED: {summary['connected']}",
            f"- PARTIAL: {summary['partial']}",
            f"- MISSING: {summary['missing']}",
            f"- BROKEN: {summary['broken']}",
            f"- Coverage: {summary['connected_pct']}%",
            "",
            "Completion Criteria:",
            f"- CONNECTED = 100%: {'PASS' if summary['connected_pct'] == 100 else 'FAIL'}",
            f"- PARTIAL = 0: {'PASS' if summary['partial'] == 0 else 'FAIL'}",
            f"- MISSING = 0: {'PASS' if summary['missing'] == 0 else 'FAIL'}",
            f"- BROKEN = 0: {'PASS' if summary['broken'] == 0 else 'FAIL'}",
            "",
        ]
    )
