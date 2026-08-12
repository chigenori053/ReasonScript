"""Phase 17 ReasonScript source subset for verified read-only graph operations."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .native_graph import query_native_graph_file, transact_native_graph_file


PROFILE = "reasonscript-reason-object-graph-language/0.1"
_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_BINDING = re.compile(rf'^reason_graph\s+({_IDENTIFIER})\s+from\s+"([^"\\]+)"(?:\s+as\s+"([^"\\]+)")?;$')
_QUERY = re.compile(rf'^query\s+({_IDENTIFIER})\s+(summary|entity|outgoing|incoming|neighbors)(?:\s+"([^"\\]+)")?;$')
_TRANSACT = re.compile(rf'^transact\s+({_IDENTIFIER})\s+"([^"\\]+)"\s+"(sha256:[0-9a-f]{{64}})"\s+"(ruo:transaction:[^"\\\s]+)";$')


def compile_graph_source(source: str) -> dict[str, Any]:
    """Parse the intentionally small, deterministic ReasonGraph operation subset."""
    lines = [(number, raw.split("//", 1)[0].strip()) for number, raw in enumerate(source.splitlines(), 1)]
    lines = [(number, line) for number, line in lines if line]
    if len(lines) < 3 or not re.fullmatch(rf"module\s+{_IDENTIFIER}\s*\{{", lines[0][1]) or lines[-1][1] != "}":
        raise ValueError("RGO-LANG-001: expected `module Name { ... }`")
    module = re.fullmatch(rf"module\s+({_IDENTIFIER})\s*\{{", lines[0][1]).group(1)  # type: ignore[union-attr]
    bindings: list[dict[str, Any]] = []
    operations: list[dict[str, Any]] = []
    names: set[str] = set()
    for line_number, line in lines[1:-1]:
        binding = _BINDING.fullmatch(line)
        if binding:
            name, source_path, expected_id = binding.groups()
            if name in names or not source_path.endswith(".rgraph") or not _safe_relative_path(source_path):
                raise ValueError("RGO-LANG-002: invalid or duplicate reason_graph binding")
            names.add(name)
            bindings.append({"node_type": "ReasonGraphBindingIR", "name": name, "source_path": source_path, "expected_graph_id": expected_id, "source_line": line_number, "capability_requirements": ["filesystem_read"]})
            continue
        query = _QUERY.fullmatch(line)
        if query:
            binding_name, operation, entity_id = query.groups()
            if binding_name not in names or (operation == "summary" and entity_id is not None) or (operation != "summary" and entity_id is None):
                raise ValueError("RGO-LANG-003: invalid ReasonGraph query binding or arguments")
            operations.append({"node_type": "ReasonGraphQueryIR", "binding_name": binding_name, "query": operation, "entity_id": entity_id, "source_line": line_number, "read_only": True})
            continue
        transaction = _TRANSACT.fullmatch(line)
        if transaction:
            binding_name, proposal_path, expected_hash, transaction_id = transaction.groups()
            if binding_name not in names or not proposal_path.endswith(".json") or not _safe_relative_path(proposal_path):
                raise ValueError("RGO-LANG-007: invalid ReasonGraph transaction")
            operations.append({"node_type": "ReasonGraphTransactionIR", "binding_name": binding_name, "proposal_path": proposal_path, "expected_graph_hash": expected_hash, "transaction_id": transaction_id, "capability_requirements": ["filesystem_read", "filesystem_write"], "read_only": False, "source_line": line_number})
            continue
        raise ValueError(f"RGO-LANG-001: unsupported ReasonGraph source statement at line {line_number}")
    if not bindings or not operations:
        raise ValueError("RGO-LANG-001: source requires at least one binding and query")
    writable = any(not operation.get("read_only", True) for operation in operations)
    return {"schema_version": PROFILE, "module": module, "bindings": bindings, "operations": operations, "capability_requirements": ["filesystem_read", *( ["filesystem_write"] if writable else [])], "read_only": not writable}


def is_graph_operation_source(source: str) -> bool:
    """Identify the explicit Phase 17 query surface without claiming generic syntax."""
    return any(line.strip().startswith(("reason_graph ", "query ")) for line in source.splitlines())


def execute_graph_source(source: str, source_path: Path, *, root: Path, filesystem_read: bool, filesystem_write: bool = False) -> dict[str, Any]:
    """Execute only verified native read-only graph queries from a compiled source."""
    if not filesystem_read:
        raise PermissionError("RGO-LANG-004: filesystem_read capability is required")
    compiled = compile_graph_source(source)
    if not compiled["read_only"] and not filesystem_write:
        raise PermissionError("RGO-LANG-008: filesystem_write capability is required")
    authorized_root = source_path.parent.resolve()
    bound: dict[str, Path] = {}
    for binding in compiled["bindings"]:
        candidate = (authorized_root / binding["source_path"]).resolve()
        if authorized_root not in candidate.parents or not candidate.is_file():
            raise ValueError("RGO-LANG-005: ReasonGraph path escapes source directory or is unavailable")
        result = query_native_graph_file(candidate, "summary", root=root)
        graph_id = result["result"]["graph_id"]
        if binding["expected_graph_id"] is not None and binding["expected_graph_id"] != graph_id:
            raise ValueError("RGO-LANG-006: expected graph ID assertion failed")
        bound[binding["name"]] = candidate
    results = []
    for operation in compiled["operations"]:
        if operation["node_type"] == "ReasonGraphQueryIR":
            result = query_native_graph_file(bound[operation["binding_name"]], operation["query"], operation["entity_id"], root=root)
            results.append({"binding_name": operation["binding_name"], "query": operation["query"], "entity_id": operation["entity_id"], "result": result["result"], "native_query": result["native_query"], "result_parity": result["report"]["result_parity"]})
        else:
            proposal = (authorized_root / operation["proposal_path"]).resolve()
            if authorized_root not in proposal.parents: raise ValueError("RGO-LANG-007: transaction proposal path escapes source directory")
            result = transact_native_graph_file(bound[operation["binding_name"]], proposal, expected_graph_hash=operation["expected_graph_hash"], transaction_id=operation["transaction_id"], root=root)
            results.append({"binding_name": operation["binding_name"], "transaction": result["transaction"], "transaction_parity": result["transaction"]["committed"] == result["expected"]["committed"]})
    return {"profile": PROFILE, "module": compiled["module"], "read_only": compiled["read_only"], "capability_decisions": ["filesystem_read:allowed", *( ["filesystem_write:allowed"] if not compiled["read_only"] else [])], "results": results}


def _safe_relative_path(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts and "\\" not in value and "://" not in value
