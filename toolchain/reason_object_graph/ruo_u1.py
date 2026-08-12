"""Non-destructive RUO-U1 to ReasonGraph integration boundary.

The generic compatibility adapter remains available for historical inputs.  This
module provides the explicit, validated boundary for a current RUO-U1 object:
only resolved Unit-to-Unit relations become canonical ReasonRelations; every
other U1 relation remains available to the reverse projection unchanged.
"""

from __future__ import annotations

import copy
from typing import Any

from toolchain.reasonunit_object.model import canonical_digest, validate_object

from .compatibility import PROFILE as COMPATIBILITY_PROFILE, project_to_graph, reverse_project
from .model import graph_hash


PROFILE = "reasonscript-reason-object-graph-ruo-u1/0.1"


def project_u1_to_graph(source: dict[str, Any]) -> dict[str, Any]:
    """Validate and project a RUO-U1 snapshot without mutating it.

    U1 relations whose endpoints are both Units receive canonical coverage.
    Relations to Payload, State, Evidence, or unavailable endpoints are retained
    in the compatibility extension, so lossless reverse projection is separate
    from canonical coverage.
    """
    if not isinstance(source, dict) or not isinstance(source.get("object_identity"), dict):
        raise ValueError("RGO-U1-001: input must be a RUO-U1 object")
    diagnostics = validate_object(source)
    if diagnostics:
        raise ValueError(f"RGO-U1-002: invalid RUO-U1 input ({diagnostics[0]['code']})")

    original = copy.deepcopy(source)
    projected = project_to_graph(source)
    if source != original:
        raise RuntimeError("RGO-U1-003: projection mutated the source")
    report = copy.deepcopy(projected["report"])
    report.update({
        "profile": PROFILE,
        "source_profile": "reasonscript-reasonunit-object-universal/1.0",
        "compatibility_profile": COMPATIBILITY_PROFILE,
        "source_object_id": source["object_identity"]["entity_id"],
        "source_revision": source.get("current_revision"),
        "source_digest": canonical_digest(source),
        "graph_hash": graph_hash(projected["graph"]),
        "promoted_relation_policy": "resolved_unit_to_unit_only",
        "retained_relation_policy": "lossless_reverse_projection_extension",
    })
    return {"graph": projected["graph"], "report": report}


def reverse_u1_projection(projection: dict[str, Any]) -> dict[str, Any]:
    """Restore the original U1 snapshot when the adapter recorded it losslessly."""
    if not isinstance(projection, dict) or projection.get("report", {}).get("profile") != PROFILE:
        raise ValueError("RGO-U1-004: projection does not use the RUO-U1 integration profile")
    return reverse_project(projection)
