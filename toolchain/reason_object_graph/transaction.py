"""Atomic copy-on-write transactions for ReasonGraph v0.1."""

from __future__ import annotations

import copy
from typing import Any

from .model import graph_hash, validate_graph


class GraphTransaction:
    """Apply a validated proposal to a ReasonGraph without partial mutation."""

    def __init__(self, graph: dict[str, Any]):
        self.graph = graph

    def commit(
        self,
        proposal: dict[str, Any],
        *,
        expected_graph_hash: str,
        transaction_id: str,
    ) -> dict[str, Any]:
        before = copy.deepcopy(self.graph)
        before_hash = graph_hash(before)
        if expected_graph_hash != before_hash:
            return self._rollback(before_hash, transaction_id, "RRG-019", "stale_graph")
        if not transaction_id.startswith("ruo:transaction:"):
            return self._rollback(before_hash, transaction_id, "RRG-019", "invalid_transaction_id")
        if not isinstance(proposal, dict):
            return self._rollback(before_hash, transaction_id, "RRG-020", "invalid_proposal")

        candidate = copy.deepcopy(before)
        try:
            changed_units, changed_relations = _apply(candidate, proposal)
        except _ProposalError as error:
            return self._rollback(before_hash, transaction_id, error.code, error.reason)

        diagnostics = validate_graph(candidate)
        if diagnostics:
            return {
                "transaction_id": transaction_id,
                "committed": False,
                "reason": "validation_failed",
                "diagnostic": diagnostics[0]["code"],
                "diagnostics": diagnostics,
                "partial_commit_count": 0,
                "graph_hash": before_hash,
            }

        self.graph.clear()
        self.graph.update(candidate)
        return {
            "transaction_id": transaction_id,
            "committed": True,
            "partial_commit_count": 0,
            "before_graph_hash": before_hash,
            "graph_hash": graph_hash(candidate),
            "changed_unit_ids": sorted(changed_units),
            "changed_relation_ids": sorted(changed_relations),
        }

    @staticmethod
    def _rollback(before_hash: str, transaction_id: str, code: str, reason: str) -> dict[str, Any]:
        return {
            "transaction_id": transaction_id,
            "committed": False,
            "reason": reason,
            "diagnostic": code,
            "partial_commit_count": 0,
            "graph_hash": before_hash,
        }


class _ProposalError(ValueError):
    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _apply(graph: dict[str, Any], proposal: dict[str, Any]) -> tuple[set[str], set[str]]:
    allowed = {"unit_additions", "relation_additions", "unit_updates", "relation_updates", "graph_updates"}
    if set(proposal) - allowed:
        raise _ProposalError("RRG-020", "unknown_proposal_operation")
    units = graph.setdefault("units", [])
    relations = graph.setdefault("relations", [])
    if not isinstance(units, list) or not isinstance(relations, list):
        raise _ProposalError("RRG-020", "invalid_graph_registry")

    unit_additions = _list(proposal, "unit_additions")
    relation_additions = _list(proposal, "relation_additions")
    unit_updates = _mapping(proposal, "unit_updates")
    relation_updates = _mapping(proposal, "relation_updates")
    graph_updates = _mapping(proposal, "graph_updates")
    if set(graph_updates) - {"root_refs", "lifecycle", "provenance", "metadata"}:
        raise _ProposalError("RRG-020", "invalid_graph_update")

    unit_index = _index(units, "unit_id")
    relation_index = _index(relations, "relation_id")
    changed_units = _apply_updates(unit_index, unit_updates, "unit_id")
    changed_relations = _apply_updates(relation_index, relation_updates, "relation_id")
    for item in unit_additions:
        if not isinstance(item, dict) or not isinstance(item.get("unit_id"), str):
            raise _ProposalError("RRG-020", "invalid_unit_addition")
        units.append(copy.deepcopy(item))
        changed_units.add(item["unit_id"])
    for item in relation_additions:
        if not isinstance(item, dict) or not isinstance(item.get("relation_id"), str):
            raise _ProposalError("RRG-020", "invalid_relation_addition")
        relations.append(copy.deepcopy(item))
        changed_relations.add(item["relation_id"])
    graph.update(copy.deepcopy(graph_updates))
    return changed_units, changed_relations


def _list(proposal: dict[str, Any], name: str) -> list[Any]:
    value = proposal.get(name, [])
    if not isinstance(value, list):
        raise _ProposalError("RRG-020", f"invalid_{name}")
    return value


def _mapping(proposal: dict[str, Any], name: str) -> dict[str, Any]:
    value = proposal.get(name, {})
    if not isinstance(value, dict) or not all(isinstance(key, str) and isinstance(patch, dict) for key, patch in value.items()):
        raise _ProposalError("RRG-020", f"invalid_{name}")
    return value


def _index(items: list[Any], identity_key: str) -> dict[str, dict[str, Any]]:
    return {item.get(identity_key): item for item in items if isinstance(item, dict) and isinstance(item.get(identity_key), str)}


def _apply_updates(index: dict[str, dict[str, Any]], updates: dict[str, Any], identity_key: str) -> set[str]:
    changed: set[str] = set()
    for identity, patch in updates.items():
        entity = index.get(identity)
        if entity is None:
            raise _ProposalError("RRG-021", "unknown_entity")
        if identity_key in patch and patch[identity_key] != identity:
            raise _ProposalError("RRG-021", "identity_mutation")
        entity.update(copy.deepcopy(patch))
        changed.add(identity)
    return changed
