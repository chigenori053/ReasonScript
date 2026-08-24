"""First-class runtime values and dispatch for the ``ruo.*`` namespace."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from toolchain.reasonunit_file import read_file, write_file
from toolchain.reasonunit_object import (
    ObjectTransaction,
    generate_execution_projection,
    query_object,
    validate_object,
)


class ReasonObjectRuntimeError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class RuntimeReasonObject:
    logical: dict[str, Any]
    source_path: Path
    resource_root: Path
    filesystem_write: bool = False

    def snapshot(self) -> "RuntimeReasonObjectSnapshot":
        return RuntimeReasonObjectSnapshot(copy.deepcopy(self.logical), self)

    def to_runtime_value(self) -> dict[str, Any]:
        return {
            "object_id": self.logical["object_identity"]["entity_id"],
            "revision_id": self.logical["current_revision"],
            "status": "loaded",
        }


@dataclass(frozen=True)
class RuntimeReasonObjectSnapshot:
    logical: dict[str, Any]
    owner: RuntimeReasonObject

    def to_runtime_value(self) -> dict[str, Any]:
        return {
            "object_id": self.logical["object_identity"]["entity_id"],
            "revision_id": self.logical["current_revision"],
            "status": "snapshot",
        }


@dataclass
class RuntimeReasonTransaction:
    snapshot: RuntimeReasonObjectSnapshot
    operations: list[dict[str, Any]] = field(default_factory=list)
    closed: bool = False

    def to_runtime_value(self) -> dict[str, Any]:
        return {
            "object_id": self.snapshot.logical["object_identity"]["entity_id"],
            "source_revision": self.snapshot.logical["current_revision"],
            "operation_count": len(self.operations),
            "status": "closed" if self.closed else "open",
        }


def load_reason_object(
    source_path: Path,
    resource_root: Path,
    *,
    filesystem_read: bool,
    filesystem_write: bool,
    expected_object_id: str | None = None,
) -> RuntimeReasonObject:
    if not filesystem_read:
        raise ReasonObjectRuntimeError("RUO-N2-007", "filesystem_read capability is required")
    root = resource_root.resolve()
    path = source_path.resolve()
    if path != root and root not in path.parents:
        raise ReasonObjectRuntimeError("RUO-N2-006", "Object path escapes resource root")
    try:
        logical = read_file(path)
    except (OSError, ValueError) as error:
        raise ReasonObjectRuntimeError("RUO-N2-013", f"Object load failed: {error}") from error
    object_id = logical.get("object_identity", {}).get("entity_id")
    if expected_object_id is not None and object_id != expected_object_id:
        raise ReasonObjectRuntimeError("RUO-N2-013", "expected Object ID assertion failed")
    return RuntimeReasonObject(logical, path, root, filesystem_write)


def _snapshot(value: Any) -> RuntimeReasonObjectSnapshot:
    if isinstance(value, RuntimeReasonObject):
        return value.snapshot()
    if isinstance(value, RuntimeReasonObjectSnapshot):
        return value
    raise ReasonObjectRuntimeError("RUO-N2-009", "operation requires ReasonObject or ReasonObjectSnapshot")


def _transaction(value: Any) -> RuntimeReasonTransaction:
    if isinstance(value, RuntimeReasonTransaction):
        if value.closed:
            raise ReasonObjectRuntimeError("RUO-N2-015", "transaction is already closed")
        return value
    return RuntimeReasonTransaction(_snapshot(value))


def _json_object(value: Any, label: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as error:
            raise ReasonObjectRuntimeError("RUO-N2-009", f"{label} must be canonical JSON") from error
        if isinstance(decoded, dict):
            return decoded
    raise ReasonObjectRuntimeError("RUO-N2-009", f"{label} must be an object")


def _resolve(logical: dict[str, Any], stable_id: str) -> Any:
    if logical.get("object_identity", {}).get("entity_id") == stable_id:
        return copy.deepcopy(logical["object_identity"])
    keys = ("entity_id", "payload_id", "state_id", "relation_id", "constraint_id", "evidence_id", "projection_id", "revision_id")
    for registry in ("units", "payloads", "states", "relations", "constraints", "evidence_registry", "projection_descriptors", "revisions"):
        for item in logical.get(registry, []):
            if any(item.get(key) == stable_id for key in keys):
                return copy.deepcopy(item)
    return None


def call_ruo(function_id: str, *args: Any) -> Any:
    method = function_id.removeprefix("ruo.")
    if method == "object_id":
        return _snapshot(args[0]).logical["object_identity"]["entity_id"]
    if method == "snapshot":
        return _snapshot(args[0])
    if method == "resolve":
        return _resolve(_snapshot(args[0]).logical, str(args[1]))
    if method == "query":
        snapshot, spec = _snapshot(args[0]), _json_object(args[1], "ReasonQuery")
        query_name = str(spec.get("query", spec.get("profile", "")))
        if query_name == "all":
            return {"entity_ids": sorted(_entity_ids(snapshot.logical))}
        try:
            return query_object(snapshot.logical, query_name, spec.get("argument"))
        except ValueError as error:
            raise ReasonObjectRuntimeError("RUO-N2-014", str(error)) from error
    if method == "begin":
        return RuntimeReasonTransaction(_snapshot(args[0]))
    if method == "apply":
        transaction = _transaction(args[0])
        transaction.operations.append(_json_object(args[1], "ReasonOperation"))
        return transaction
    if method == "validate":
        transaction = _transaction(args[0])
        candidate = _candidate(transaction)
        diagnostics = validate_object(candidate)
        return {"valid": not diagnostics, "diagnostics": diagnostics, "operation_count": len(transaction.operations)}
    if method == "commit":
        transaction = _transaction(args[0])
        state_updates: dict[str, Any] = {}
        transaction_id = f"ruo:transaction:runtime-{len(transaction.snapshot.owner.logical.get('revisions', [])) + 1}"
        for operation in transaction.operations:
            state_updates.update(operation.get("state_updates", {}))
            transaction_id = str(operation.get("transaction_id", transaction_id))
        result = ObjectTransaction(transaction.snapshot.owner.logical).commit(
            {"state_updates": state_updates},
            source_revision=transaction.snapshot.logical["current_revision"],
            transaction_id=transaction_id,
        )
        transaction.closed = True
        return result
    if method == "rollback":
        transaction = _transaction(args[0]); transaction.closed = True
        return {"committed": False, "rolled_back": True, "partial_commit_count": 0}
    if method in {"select", "materialize"}:
        snapshot, selector = _snapshot(args[0]), _json_object(args[1], "ReasonSelector")
        selected = set(map(str, selector.get("entity_ids", [])))
        if not selected:
            selected = _entity_ids(snapshot.logical)
        return {"entity_ids": sorted(selected & _entity_ids(snapshot.logical)), "materialized": method == "materialize"}
    if method == "project":
        return generate_execution_projection(_snapshot(args[0]).logical)
    if method == "save":
        snapshot, target_value, policy = _snapshot(args[0]), str(args[1]), str(args[2])
        owner = snapshot.owner
        if not owner.filesystem_write:
            raise ReasonObjectRuntimeError("RUO-N2-007", "filesystem_write capability is required")
        target = (owner.resource_root / target_value).resolve()
        if target != owner.resource_root and owner.resource_root not in target.parents:
            raise ReasonObjectRuntimeError("RUO-N2-006", "save path escapes resource root")
        receipt = write_file(snapshot.logical, target, overwrite=policy in {"overwrite", "allow", "replace"})
        return {"committed": True, "path": receipt["path"], "sha256": receipt["sha256"]}
    if method == "tensor_view":
        payload = _resolve(_snapshot(args[0]).logical, str(args[1]))
        if not isinstance(payload, dict) or not str(payload.get("profile_id", "")).startswith("ruo.payload.tensor"):
            raise ReasonObjectRuntimeError("RUO-N2-014", "Tensor payload not found")
        return copy.deepcopy(payload.get("value", payload.get("value_ref", payload)))
    if method == "status":
        if isinstance(args[0], RuntimeReasonObject): return "loaded"
        if isinstance(args[0], RuntimeReasonObjectSnapshot): return "snapshot"
        if isinstance(args[0], RuntimeReasonTransaction): return "closed" if args[0].closed else "open"
        return "value" if args[0] is not None else "absent"
    if method == "diagnostics":
        return []
    raise ReasonObjectRuntimeError("RUO-N2-009", f"unknown ruo standard function: {function_id}")


def _candidate(transaction: RuntimeReasonTransaction) -> dict[str, Any]:
    candidate = copy.deepcopy(transaction.snapshot.logical)
    states = {item.get("state_id"): item for item in candidate.get("states", [])}
    for operation in transaction.operations:
        for state_id, state_value in operation.get("state_updates", {}).items():
            if state_id in states:
                states[state_id]["value"] = copy.deepcopy(state_value)
    return candidate


def _entity_ids(logical: dict[str, Any]) -> set[str]:
    result = {str(logical.get("object_identity", {}).get("entity_id", ""))}
    for registry in ("units", "payloads", "states", "relations", "constraints", "evidence_registry", "projection_descriptors", "revisions"):
        for item in logical.get(registry, []):
            for key in ("entity_id", "payload_id", "state_id", "relation_id", "constraint_id", "evidence_id", "projection_id", "revision_id"):
                if key in item: result.add(str(item[key])); break
    result.discard("")
    return result
