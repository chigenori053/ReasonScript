"""Bridge to the versioned Rust ``reason-runtime-host`` protocol.

Resolves the source-tree or installed runtime host and runs it
against a `reason-computation-ir/0.1` document, for differentially
testing it against the Python IR interpreter
(`frontend.computation_ir.interpreter`). Mirrors the candidate-path
pattern `toolchain.native_runtime.native_reasonunit_runtime_candidates`
already uses for the (unrelated) native ReasonUnit Runtime binary.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

_CRATE_ROOT = Path(__file__).resolve().parents[2] / "ReasonComputationRuntime"
_DISTRIBUTION_ROOT = Path(__file__).resolve().parents[2]


def binary_name() -> str:
    return "reason-runtime-host.exe" if os.name == "nt" else "reason-runtime-host"


def binary_candidates() -> tuple[Path, ...]:
    name = binary_name()
    configured = os.environ.get("REASONSCRIPT_RUNTIME_HOST")
    home = os.environ.get("REASONSCRIPT_HOME")
    path_candidate = shutil.which(name)
    candidates = [
        Path(configured) if configured else None,
        Path(home) / "current" / "bin" / name if home else None,
        _DISTRIBUTION_ROOT / "bin" / name,
        _CRATE_ROOT / "target" / "release" / name,
        _CRATE_ROOT / "target" / "debug" / name,
        Path(path_candidate) if path_candidate else None,
    ]
    return tuple(candidate for candidate in candidates if candidate is not None)


def find_binary() -> Path | None:
    for candidate in binary_candidates():
        if candidate.is_file():
            return candidate
    return None


class RustRunResult:
    def __init__(self, ok: bool, calculation_results: dict[str, Any] | None, error_code: str | None, error_message: str | None):
        self.ok = ok
        self.calculation_results = calculation_results
        self.error_code = error_code
        self.error_message = error_message


def run_ir(
    ir_document: dict[str, Any],
    *,
    binary: Path | None = None,
    cwd: Path | None = None,
    filesystem_read: bool = True,
    filesystem_write: bool = True,
) -> RustRunResult:
    resolved = binary or find_binary()
    if resolved is None:
        raise FileNotFoundError(
            "reason-computation-runtime binary not found; searched: "
            + ", ".join(str(candidate) for candidate in binary_candidates())
            + ". Build it with: cargo build --manifest-path ReasonComputationRuntime/Cargo.toml"
        )
    request_id = "python-bridge"
    request = {
        "schema": "reasonscript-runtime-request/1.0",
        "request_id": request_id,
        "operation": "execute",
        "program": ir_document,
        "context": {
            "resource_root": str(cwd.resolve()) if cwd is not None else str(Path.cwd().resolve()),
            "capabilities": {
                "filesystem_read": filesystem_read,
                "filesystem_write": filesystem_write,
                "network": False,
            },
            "limits": {},
            "trace": {"enabled": False},
            "numeric_mode": os.environ.get("REASONSCRIPT_NUMERIC_MODE", "compat-reference"),
        },
    }
    completed = subprocess.run(
        [str(resolved)],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        timeout=30,
        cwd=str(cwd) if cwd is not None else None,
    )
    payload = json.loads(completed.stdout)
    if payload.get("ok"):
        return RustRunResult(True, payload["calculation_results"], None, None)
    diagnostics = payload.get("diagnostics", [])
    diagnostic = diagnostics[0] if diagnostics else {}
    return RustRunResult(
        False,
        None,
        diagnostic.get("code", payload.get("error_code")),
        diagnostic.get("message", payload.get("error_message")),
    )
