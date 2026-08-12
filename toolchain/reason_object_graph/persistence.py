"""Atomic optimistic transactions over canonical RGO-F1 files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .format import read_graph, write_graph
from .transaction import GraphTransaction


PROFILE = "reasonscript-reason-object-graph-persistence/0.1"


def transact_graph_file(
    path: Path,
    proposal: dict[str, Any],
    *,
    expected_graph_hash: str,
    transaction_id: str,
) -> dict[str, Any]:
    """Commit a graph proposal to its existing RGO-F1 path or retain prior bytes."""
    graph = read_graph(path)
    before_bytes = path.read_bytes()
    result = GraphTransaction(graph).commit(
        proposal, expected_graph_hash=expected_graph_hash, transaction_id=transaction_id,
    )
    result["profile"] = PROFILE
    result["path"] = str(path)
    if not result["committed"]:
        if path.read_bytes() != before_bytes:
            raise RuntimeError("RGO-PERSIST-001: rejected transaction modified the RGO-F1 file")
        result["source_bytes_unchanged"] = True
        return result
    publication = write_graph(graph, path, overwrite=True)
    result["publication"] = publication
    result["source_bytes_unchanged"] = False
    return result
