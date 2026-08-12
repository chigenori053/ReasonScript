"""Native Runtime parity check for the read-only ReasonGraph handoff."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from toolchain.native_runtime import native_reasonunit_runtime_name, resolve_native_reasonunit_runtime

from .ruo_f1 import project_ruo_file


PROFILE = "reasonscript-reason-object-graph-native-handoff/0.1"


def project_native_ruo_file(path: Path, *, root: Path | None = None) -> dict[str, Any]:
    """Cross-check Native Runtime metadata against the canonical graph projection."""
    binary = _native_binary(root)
    completed = subprocess.run(
        [str(binary), "reason-graph-handoff", str(path)], cwd=root,
        capture_output=True, text=True, timeout=30, check=False,
    )
    try:
        native = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("RGO-NATIVE-001: Native Runtime did not emit JSON") from error
    if completed.returncode != 0 or not native.get("ok"):
        raise ValueError("RGO-NATIVE-001: Native Runtime rejected RUO-F1 input")
    handoff = native.get("reason_graph_handoff")
    if not isinstance(handoff, dict) or handoff.get("profile") != PROFILE:
        raise ValueError("RGO-NATIVE-002: Native Runtime handoff is missing or incompatible")
    projection = project_ruo_file(path)
    graph = projection["graph"]
    native_units = sorted(item for item in handoff.get("unit_ids", []) if isinstance(item, str))
    graph_units = sorted(unit["unit_id"] for unit in graph["units"])
    if native_units != graph_units:
        raise ValueError("RGO-NATIVE-003: Native Runtime Unit identities do not match ReasonGraph")
    source_digest = projection["report"]["source_file_verification"]["logical_object_digest"]
    if handoff.get("logical_object_digest") != source_digest:
        raise ValueError("RGO-NATIVE-004: Native Runtime logical digest does not match RUO-F1")
    report = dict(projection["report"])
    report.update({
        "native_handoff_profile": PROFILE,
        "native_runtime_profile": native["native_execution_provenance"],
        "native_snapshot_generation": native["snapshot_generation"],
        "native_unit_identity_parity": True,
        "native_logical_digest_parity": True,
    })
    return {"graph": graph, "report": report, "native_handoff": handoff}


def _native_binary(root: Path | None) -> Path:
    """Prefer the explicitly supplied source tree; distribution resolution is fallback."""
    if root is not None:
        candidate = root / "NativeReasonUnitRuntime" / "target" / "debug" / native_reasonunit_runtime_name()
        if candidate.is_file():
            return candidate
    return resolve_native_reasonunit_runtime()
