"""Read-only RUO-F1 file to ReasonGraph integration boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from toolchain.reasonunit_file import read_file, validate_file

from .format import write_graph
from .ruo_u1 import PROFILE as RUO_U1_PROFILE, project_u1_to_graph


PROFILE = "reasonscript-reason-object-graph-ruo-f1/0.1"


def project_ruo_file(path: Path) -> dict[str, Any]:
    """Verify a complete canonical RUO-F1 file, then project it read-only."""
    verification = validate_file(path, mode="strict")
    if not verification["ok"] or verification.get("semantic_status") != "VALID":
        code = verification.get("diagnostics", [{}])[0].get("code", "RGO-F1-001")
        raise ValueError(f"RGO-F1-001: RUO-F1 validation failed ({code})")
    projection = project_u1_to_graph(read_file(path, mode="strict"))
    report = dict(projection["report"])
    report.update({
        "profile": PROFILE,
        "source_profile": "reasonscript-reasonunit-object-file/1.0",
        "ruo_u1_integration_profile": RUO_U1_PROFILE,
        "source_path": path.name,
        "source_file_verification": {
            "format_version": verification["format_version"],
            "object_id": verification["object_id"],
            "object_revision_id": verification["object_revision_id"],
            "logical_object_digest": verification["digests"]["logical_object_digest"],
            "content_stream_sha256": verification["digests"]["content_stream_sha256"],
        },
    })
    return {"graph": projection["graph"], "report": report}


def project_ruo_file_to_rgraph(source: Path, target: Path, *, overwrite: bool = False) -> dict[str, Any]:
    """Project a verified RUO-F1 source and atomically publish an RGO-F1 graph."""
    projection = project_ruo_file(source)
    publication = write_graph(projection["graph"], target, overwrite=overwrite)
    return {**projection, "publication": {"ok": True, **publication}}
