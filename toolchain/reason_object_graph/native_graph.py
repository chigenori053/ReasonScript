"""Native Runtime verification for immutable RGO-F1 graph loading."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from toolchain.native_runtime import native_reasonunit_runtime_name, resolve_native_reasonunit_runtime

from .format import read_graph
from .model import graph_hash
from .query import query_graph
from .transaction import GraphTransaction


PROFILE = "reasonscript-reason-object-graph-native/0.1"


def load_native_graph_file(path: Path, *, root: Path | None = None) -> dict[str, Any]:
    """Load an RGO-F1 file natively and prove its identity parity with Python."""
    binary = _native_binary(root)
    completed = subprocess.run(
        [str(binary), "load-graph", str(path)], cwd=root,
        capture_output=True, text=True, timeout=30, check=False,
    )
    try:
        native = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("RGO-NATIVE-GRAPH-001: Native Runtime did not emit JSON") from error
    if completed.returncode != 0 or not native.get("ok"):
        diagnostic = native.get("diagnostics", [{}])[0]
        message = diagnostic.get("message", "Native Runtime rejected RGO-F1 input") if isinstance(diagnostic, dict) else "Native Runtime rejected RGO-F1 input"
        raise ValueError(f"RGO-NATIVE-GRAPH-001: Native Runtime rejected RGO-F1 input: {message}")
    if native.get("native_reason_graph_profile") != PROFILE or native.get("read_only") is not True:
        raise ValueError("RGO-NATIVE-GRAPH-002: Native graph loader is missing or incompatible")
    graph = read_graph(path)
    graph_units = sorted(unit["unit_id"] for unit in graph["units"])
    graph_relations = sorted(relation["relation_id"] for relation in graph["relations"])
    if native.get("graph_id") != graph["graph_id"] or native.get("graph_hash") != graph_hash(graph):
        raise ValueError("RGO-NATIVE-GRAPH-003: Native Runtime graph identity does not match RGO-F1")
    if native.get("unit_ids") != graph_units or native.get("relation_ids") != graph_relations:
        raise ValueError("RGO-NATIVE-GRAPH-004: Native Runtime graph entities do not match RGO-F1")
    return {
        "graph": graph,
        "native_graph": native,
        "report": {
            "profile": PROFILE,
            "native_runtime_profile": native["native_execution_provenance"],
            "graph_identity_parity": True,
            "graph_entity_identity_parity": True,
            "read_only": True,
        },
    }


def query_native_graph_file(path: Path, query: str, entity_id: str | None = None, *, root: Path | None = None) -> dict[str, Any]:
    """Run a native read-only query and compare its result to the Python contract."""
    binary = _native_binary(root)
    command = [str(binary), "query-graph", str(path), query]
    if entity_id is not None:
        command.append(entity_id)
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30, check=False)
    try:
        native = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("RGO-NATIVE-QUERY-001: Native Runtime did not emit JSON") from error
    if completed.returncode != 0 or not native.get("ok"):
        raise ValueError("RGO-NATIVE-QUERY-001: Native Runtime rejected query")
    native_result = native.get("query_result")
    if not isinstance(native_result, dict) or native_result.get("profile") != "reasonscript-reason-object-graph-native-query/0.1":
        raise ValueError("RGO-NATIVE-QUERY-002: Native Runtime query response is incompatible")
    graph = read_graph(path)
    expected = query_graph(graph, query, entity_id)
    if native_result.get("graph_id") != expected["graph_id"] or native_result.get("graph_hash") != expected["graph_hash"]:
        raise ValueError("RGO-NATIVE-QUERY-003: Native Runtime query graph identity mismatch")
    if native_result.get("query") != query or native_result.get("entity_id") != entity_id or native_result.get("result") != expected["result"]:
        raise ValueError("RGO-NATIVE-QUERY-004: Native Runtime query result does not match ReasonGraph")
    return {
        "graph": graph,
        "native_query": native,
        "result": expected,
        "report": {
            "profile": "reasonscript-reason-object-graph-native-query/0.1",
            "query": query,
            "result_parity": True,
            "read_only": True,
        },
    }


def transact_native_graph_file(path: Path, proposal_path: Path, *, expected_graph_hash: str, transaction_id: str, root: Path | None = None) -> dict[str, Any]:
    """Compare native metadata compare-and-commit with the Phase 13 contract."""
    before_bytes = path.read_bytes()
    before_graph = read_graph(path)
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    expected = GraphTransaction(before_graph).commit(proposal, expected_graph_hash=expected_graph_hash, transaction_id=transaction_id)
    binary = _native_binary(root)
    completed = subprocess.run(
        [str(binary), "transact-graph", str(path), str(proposal_path), expected_graph_hash, transaction_id],
        cwd=root, capture_output=True, text=True, timeout=30, check=False,
    )
    try:
        native = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("RGO-NATIVE-TX-001: Native Runtime did not emit JSON") from error
    transaction = native.get("transaction")
    if not isinstance(transaction, dict):
        raise ValueError("RGO-NATIVE-TX-001: Native Runtime did not return a transaction")
    if bool(transaction.get("committed")) != bool(expected.get("committed")):
        raise ValueError("RGO-NATIVE-TX-002: Native transaction outcome does not match ReasonGraph")
    if not transaction.get("committed"):
        if path.read_bytes() != before_bytes or transaction.get("source_bytes_unchanged") is not True:
            raise ValueError("RGO-NATIVE-TX-003: Rejected native transaction modified RGO-F1")
    else:
        graph = read_graph(path)
        if graph_hash(graph) != expected.get("graph_hash") or transaction.get("graph_hash") != expected.get("graph_hash"):
            raise ValueError("RGO-NATIVE-TX-004: Native committed graph hash does not match ReasonGraph")
    return {"native_transaction": native, "transaction": transaction, "expected": expected, "read_only": False}


def _native_binary(root: Path | None) -> Path:
    if root is not None:
        candidate = root / "NativeReasonUnitRuntime" / "target" / "debug" / native_reasonunit_runtime_name()
        if candidate.is_file():
            return candidate
    return resolve_native_reasonunit_runtime()
