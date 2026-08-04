"""Typed RUO-N2 source, IR, plan, capability, and native binding helpers."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from toolchain.native_runtime import resolve_native_reasonunit_runtime

from frontend.language_surface import compile_program, execution_plan_for, parse, to_json_value
from frontend.language_surface.nodes import ReasonObjectBindingNode

PROFILE = "reasonscript-reasonunit-language-integration/1.0"
NATIVE_PROFILE = "reasonscript-reasonunit-native-runtime/1.0"
RUO_TYPES = (
    "ReasonObject", "ReasonObjectSnapshot", "ReasonEntityRef", "ReasonQuery",
    "ReasonQueryResult", "ReasonTransaction", "ReasonTransactionResult",
    "ReasonSelector", "ReasonSelection", "ReasonProjection", "ReasonTensorView",
    "ReasonDiagnosticSet",
)
PRESENCE_STATES = ("value", "absent", "not_loaded", "unavailable", "unknown", "invalid", "deleted", "stale", "conflict", "error")
RUO_FUNCTIONS = (
    ("object_id", "ReasonObject", "StableId"), ("snapshot", "ReasonObject", "ReasonObjectSnapshot"),
    ("resolve", "ReasonObjectSnapshot,StableId", "ReasonEntityRef"), ("query", "ReasonObjectSnapshot,ReasonQuery", "ReasonQueryResult"),
    ("begin", "ReasonObjectSnapshot", "ReasonTransaction"), ("apply", "ReasonTransaction,ReasonOperation", "ReasonTransaction"),
    ("validate", "ReasonTransaction", "ReasonTransactionResult"), ("commit", "ReasonTransaction", "ReasonTransactionResult"),
    ("rollback", "ReasonTransaction", "ReasonTransactionResult"), ("select", "ReasonObjectSnapshot,ReasonSelector", "ReasonSelection"),
    ("materialize", "ReasonObjectSnapshot,ReasonSelector", "ReasonSelection"), ("project", "ReasonObjectSnapshot,ReasonProjectionProfile", "ReasonProjection"),
    ("save", "ReasonObjectSnapshot,Path,OverwritePolicy", "ReasonTransactionResult"), ("tensor_view", "ReasonObjectSnapshot,StableId,ReasonSelector?", "ReasonTensorView"),
    ("status", "ReasonValue", "ReasonStatus"), ("diagnostics", "ReasonValue", "ReasonDiagnosticSet"),
)
DEFAULT_LIMITS = {"source_bytes": 1_000_000, "bindings": 256, "path_bytes": 4096, "diagnostics": 1000, "query_results": 100_000, "transaction_operations": 10_000, "selector_closure": 100_000, "projection_size": 100_000, "tensor_view_bytes": 256_000_000}


def standard_function_registry() -> list[dict[str, Any]]:
    return [{"name": f"ruo.{name}", "version": "1.0", "input_type": input_type, "output_type": output_type, "native_operation": name, "determinism": "deterministic", "failure_states": list(PRESENCE_STATES[1:])} for name, input_type, output_type in RUO_FUNCTIONS]


def compile_reason_object_source(source: str, *, limits: dict[str, int] | None = None) -> dict[str, Any]:
    configured = {**DEFAULT_LIMITS, **(limits or {})}
    if len(source.encode()) > configured["source_bytes"]: raise ValueError("RUO-N2-022 source byte limit exceeded")
    program = parse(source); ast = to_json_value(program); irs = compile_program(program)
    bindings = [binding for ir in irs for binding in ir.get("metadata", {}).get("reason_object_bindings", [])]
    if len(bindings) > configured["bindings"]: raise ValueError("RUO-N2-022 binding count limit exceeded")
    if any(len(binding["logical_source_ref"].encode()) > configured["path_bytes"] for binding in bindings): raise ValueError("RUO-N2-022 path length limit exceeded")
    return {"schema_version": PROFILE, "surface_ast": ast, "reason_ir": list(irs), "execution_plans": [execution_plan_for(ir) for ir in irs], "bindings": bindings, "static_types": list(RUO_TYPES), "standard_functions": standard_function_registry()}


def _nodes(source: str) -> list[ReasonObjectBindingNode]:
    return [node for module in parse(source).modules for node in module.body if isinstance(node, ReasonObjectBindingNode)]


def bind_source_objects(source: str, source_path: Path, root: Path, *, filesystem_read: bool, load_profile: str = "lazy_verified") -> list[dict[str, Any]]:
    if load_profile not in {"eager_verified", "lazy_verified", "metadata_only"}: raise ValueError("RUO-N2-011 invalid load profile")
    if not filesystem_read: raise PermissionError("RUO-N2-007 filesystem_read capability is required")
    authorized = root.resolve(); binary = resolve_native_reasonunit_runtime()
    results = []
    for node in _nodes(source):
        candidate = (source_path.parent / node.source_path).resolve()
        if candidate != authorized and authorized not in candidate.parents: raise PermissionError("RUO-N2-006 Object path escapes authorized root")
        completed = subprocess.run([str(binary), "inspect" if load_profile == "metadata_only" else "load", str(candidate)], cwd=root, capture_output=True, text=True, timeout=30, check=False)
        try: native = json.loads(completed.stdout)
        except json.JSONDecodeError: native = {"ok": False, "diagnostics": [{"code": "RUO-N2-012", "message": completed.stderr or "invalid native output"}]}
        if not native.get("ok"): raise ValueError(f"RUO-N2-013 native load failed: {native.get('diagnostics', [])}")
        if node.expected_object_id is not None and native.get("object_id") != node.expected_object_id: raise ValueError("RUO-N2-013 expected Object ID assertion failed")
        results.append({"binding_name": node.name, "binding_id": next(binding["binding_id"] for binding in compile_reason_object_source(source)["bindings"] if binding["lexical_name"] == node.name), "object_id": native.get("object_id"), "revision_id": native.get("revision_id"), "snapshot_generation": native.get("snapshot_generation"), "load_mode": node.load_mode, "load_profile": load_profile, "capability_decision": "filesystem_read:allowed", "native_execution_provenance": native.get("native_execution_provenance"), "source_span": to_json_value(node.source_span), "native_result": native})
    return results


def format_reason_object_source(source: str) -> str:
    if "reason_object" not in source: return source
    nodes = _nodes(source); by_name = {node.name: node for node in nodes}
    lines = source.splitlines(); output: list[str] = []; index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        match = re.match(r"reason_object\s+([A-Za-z_][A-Za-z0-9_]*)\b", stripped)
        if not match:
            output.append(lines[index]); index += 1; continue
        node = by_name[match.group(1)]; indent = lines[index][:len(lines[index]) - len(lines[index].lstrip())]
        output.append(f'{indent}reason_object {node.name} from "{node.source_path}"')
        if node.resource_root is not None: output.append(f'{indent}    resources "{node.resource_root}"')
        output.append(f"{indent}    mode {node.load_mode}")
        if node.expected_object_id is not None: output.append(f'{indent}    as "{node.expected_object_id}";')
        else: output[-1] += ";"
        index += 1
        while index < len(lines) and re.match(r"^(resources|mode|as)\b", lines[index].strip()): index += 1
    return "\n".join(output) + ("\n" if source.endswith("\n") else "")
