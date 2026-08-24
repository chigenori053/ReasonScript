"""Capability-checked bridge from integrated execution to Rust ReasonRuntime/crates/vision-core."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from toolchain.reasonunit_file import write_file
from toolchain.reasonunit_object.model import validate_object


class VisionRuntimeError(ValueError):
    def __init__(self, code: str, message: str, *, stage: str = "runtime"):
        self.code = code
        self.stage = stage
        self.message = message
        super().__init__(f"{code} {message}")

    def diagnostic(self) -> dict[str, Any]:
        return {"code": self.code, "severity": "fatal", "category": "vision.runtime", "message": self.message, "stage": self.stage}


class VisionRuntimeBridge:
    def __init__(self, root: Path, *, filesystem_read: bool = False, filesystem_write: bool = False):
        self.root = root.resolve()
        self.filesystem_read = filesystem_read
        self.filesystem_write = filesystem_write
        self.trace: list[dict[str, Any]] = []

    def call(self, function: str, *arguments: Any) -> Any:
        if function == "vision.infer":
            return self.infer(*arguments)
        if function == "vision.build_ruo":
            return self.build_ruo(*arguments)
        raise VisionRuntimeError("VIS-LANG-001", f"unknown Vision function: {function}")

    def infer(self, model_path: str, image_path: str) -> dict[str, Any]:
        if not self.filesystem_read:
            raise VisionRuntimeError("VIS-CAP-001", "vision.infer requires filesystem_read capability", stage="capability")
        model = self._resolve(model_path)
        image = self._resolve(image_path)
        result = self._native(["infer", str(model), str(image)])
        observation = result.get("observation")
        if not isinstance(observation, dict):
            raise VisionRuntimeError("VIS-RUN-003", "native inference returned no observation")
        self.trace.append({"operation": "vision_infer", "model": model_path, "image": image_path, "observation_id": observation.get("observation_id"), "native_profile": result.get("profile")})
        return observation

    def build_ruo(self, observation: dict[str, Any], output_path: str) -> dict[str, Any]:
        if not self.filesystem_write:
            raise VisionRuntimeError("VIS-CAP-002", "vision.build_ruo requires filesystem_write capability", stage="capability")
        if not isinstance(observation, dict):
            raise VisionRuntimeError("VIS-LANG-005", "vision.build_ruo requires VisionObservation")
        output = self._resolve(output_path)
        if output.suffix != ".ruo":
            raise VisionRuntimeError("VIS-LANG-004", "Vision Object output must use lowercase .ruo", stage="path")
        if output.exists():
            raise VisionRuntimeError("VIS-PUB-001", "Vision Object output already exists", stage="publication")
        output.parent.mkdir(parents=True, exist_ok=True)
        published: list[Path] = []
        try:
            with tempfile.TemporaryDirectory(prefix="vision-runtime-") as temporary:
                staging = Path(temporary)
                observation_path = staging / "observation.json"
                observation_path.write_text(json.dumps(observation, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
                bundle_dir = staging / "bundle"
                self._native(["build-ruo", str(observation_path), "--output", str(bundle_dir)])
                logical = json.loads((bundle_dir / "vision_object.json").read_text(encoding="utf-8"))
                diagnostics = validate_object(logical)
                if diagnostics:
                    raise VisionRuntimeError("VIS-PUB-002", "generated Object failed RUO-U1 validation", stage="publication")
                for resource in logical.get("external_resources", []):
                    locator = self._safe_locator(resource.get("locator"))
                    source = bundle_dir / locator
                    target = output.parent / locator
                    expected = str(resource.get("content_sha256", "")).removeprefix("sha256:")
                    data = source.read_bytes()
                    if hashlib.sha256(data).hexdigest() != expected:
                        raise VisionRuntimeError("VIS-PUB-003", "Tensor resource digest mismatch", stage="publication")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists():
                        if target.read_bytes() != data:
                            raise VisionRuntimeError("VIS-PUB-004", f"resource already exists with different bytes: {locator}", stage="publication")
                        continue
                    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
                    try:
                        with os.fdopen(fd, "wb") as handle:
                            handle.write(data); handle.flush(); os.fsync(handle.fileno())
                        os.replace(temporary_name, target); published.append(target)
                    finally:
                        if os.path.exists(temporary_name): os.unlink(temporary_name)
                write_file(logical, output, overwrite=False)
            result = {"status": "committed", "object_id": logical["object_identity"]["entity_id"], "path": output_path, "profile": "reasonscript-vision-build-result/0.1"}
            self.trace.append({"operation": "vision_build_ruo", "output": output_path, "object_id": result["object_id"], "transaction_boundary": "atomic_ruo_f1"})
            return result
        except Exception:
            if not output.exists():
                for path in reversed(published):
                    try: path.unlink()
                    except FileNotFoundError: pass
            raise

    def _resolve(self, value: str) -> Path:
        if not isinstance(value, str):
            raise VisionRuntimeError("VIS-LANG-003", "Vision path argument must be string", stage="path")
        pure = PurePosixPath(value)
        if not value or "\\" in value or pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise VisionRuntimeError("VIS-SEC-001", "unsafe Vision path", stage="path")
        candidate = (self.root / pure).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise VisionRuntimeError("VIS-SEC-001", "Vision path escapes project root", stage="path")
        return candidate

    @staticmethod
    def _safe_locator(value: Any) -> PurePosixPath:
        if not isinstance(value, str) or not value or "\\" in value:
            raise VisionRuntimeError("VIS-SEC-002", "unsafe Tensor resource locator", stage="path")
        pure = PurePosixPath(value)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise VisionRuntimeError("VIS-SEC-002", "unsafe Tensor resource locator", stage="path")
        return pure

    def _native(self, arguments: list[str]) -> dict[str, Any]:
        repository = Path(__file__).resolve().parents[2]
        crate = repository / "ReasonRuntime"
        binary_name = "reason-vision.exe" if os.name == "nt" else "reason-vision"
        installed_binary = repository / "bin" / binary_name
        release_binary = crate / "target" / "release" / binary_name
        debug_binary = crate / "target" / "debug" / binary_name
        binary = installed_binary if installed_binary.is_file() else (release_binary if release_binary.is_file() else debug_binary)
        sources = [crate / "Cargo.toml", *(crate / "src").glob("*.rs")]
        current = installed_binary.is_file() or (binary.is_file() and binary.stat().st_mtime_ns >= max(path.stat().st_mtime_ns for path in sources))
        command = [str(binary), *arguments] if current else ["cargo", "run", "--offline", "--quiet", "--manifest-path", str(crate / "Cargo.toml"), "--bin", "reason-vision", "--", *arguments]
        completed = subprocess.run(command, cwd=repository, capture_output=True, text=True, timeout=60, check=False)
        try: result = json.loads(completed.stdout)
        except json.JSONDecodeError as error: raise VisionRuntimeError("VIS-RUN-004", completed.stderr or "native Vision output invalid") from error
        if not result.get("ok"):
            diagnostic = next(iter(result.get("diagnostics", [])), {})
            raise VisionRuntimeError(str(diagnostic.get("code", "VIS-RUN-005")), str(diagnostic.get("message", "native Vision operation failed")), stage=str(diagnostic.get("stage", "runtime")))
        return result
