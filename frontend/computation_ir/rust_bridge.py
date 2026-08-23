"""Bridge to the Phase 3 Rust `reason-computation-runtime` CLI.

Resolves the compiled `reason-computation-runtime` binary and runs it
against a `reason-computation-ir/0.1` document, for differentially
testing it against the Python IR interpreter
(`frontend.computation_ir.interpreter`). Mirrors the candidate-path
pattern `toolchain.native_runtime.native_reasonunit_runtime_candidates`
already uses for the (unrelated) native ReasonUnit Runtime binary.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

_CRATE_ROOT = Path(__file__).resolve().parents[2] / "ReasonComputationRuntime"


def binary_name() -> str:
    return "reason-computation-runtime.exe" if os.name == "nt" else "reason-computation-runtime"


def binary_candidates() -> tuple[Path, ...]:
    name = binary_name()
    return (
        _CRATE_ROOT / "target" / "release" / name,
        _CRATE_ROOT / "target" / "debug" / name,
    )


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


def run_ir(ir_document: dict[str, Any], *, binary: Path | None = None) -> RustRunResult:
    resolved = binary or find_binary()
    if resolved is None:
        raise FileNotFoundError(
            "reason-computation-runtime binary not found; searched: "
            + ", ".join(str(candidate) for candidate in binary_candidates())
            + ". Build it with: cargo build --manifest-path ReasonComputationRuntime/Cargo.toml"
        )
    completed = subprocess.run(
        [str(resolved)],
        input=json.dumps(ir_document),
        text=True,
        capture_output=True,
        timeout=30,
    )
    payload = json.loads(completed.stdout)
    if payload.get("ok"):
        return RustRunResult(True, payload["calculation_results"], None, None)
    return RustRunResult(False, None, payload.get("error_code"), payload.get("error_message"))
