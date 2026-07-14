"""Narrow platform adapter boundary for installation updates."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def platform_id() -> str:
    return {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(
        platform.system(), platform.system().lower()
    )


def architecture_id() -> str:
    return {
        "AMD64": "x86_64",
        "x64": "x86_64",
        "x86_64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(platform.machine(), platform.machine().lower())


@dataclass(frozen=True)
class PlatformAdapter:
    name: str
    architecture: str

    def default_install_root(self) -> Path:
        configured = os.environ.get("REASONSCRIPT_HOME")
        if configured:
            return Path(configured).expanduser().resolve()
        if self.name == "windows":
            return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ReasonScript"
        return Path.home() / ".reasonscript"

    def launcher_path(self, root: Path) -> Path:
        return root / "bin" / ("reason.cmd" if self.name == "windows" else "reason")

    def prepare_install_root(self, root: Path) -> None:
        for relative in ("versions", "staging", "backup", "config", "metadata", "artifacts/install"):
            (root / relative).mkdir(parents=True, exist_ok=True)

    def prepare_staging(self, staging: Path) -> None:
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)

    def ensure_executable(self, path: Path) -> None:
        if self.name != "windows" and path.is_file():
            path.chmod(path.stat().st_mode | 0o111)

    def validate_permissions(self, root: Path) -> bool:
        target = root if root.exists() else root.parent
        return os.access(target, os.W_OK)

    def detect_running_process_conflict(self) -> bool:
        # Version directories and the fixed launcher avoid replacing the running CLI.
        return False

    def atomic_json_write(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            Path(temporary_name).replace(path)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise

    def activate_version(self, root: Path, version: str, previous: str | None) -> None:
        target = root / "versions" / version
        if not target.is_dir():
            raise OSError(f"version directory does not exist: {target}")
        updater = root / "bin" / ("reason-updater.exe" if self.name == "windows" else "reason-updater")
        if updater.is_file():
            process = subprocess.run(
                [str(updater), "activate", str(root), version, previous or "-"],
                text=True, capture_output=True,
            )
            if process.returncode:
                raise OSError(process.stderr.strip() or "native activation helper failed")
        else:
            current_payload = {
                "schema_version": "reasonscript-current-installation/1.0",
                "active_version": version,
                "previous_version": previous,
                "activation_status": "active",
            }
            self.atomic_json_write(root / "metadata/current.json", current_payload)
        # v1.0 compatibility: keep <root>/current available for older callers.
        current = root / "current"
        temporary = root / f".current-{os.getpid()}"
        backup = root / f".current-old-{os.getpid()}"
        for path in (temporary, backup):
            if path.exists() or path.is_symlink():
                path.unlink() if path.is_symlink() or path.is_file() else shutil.rmtree(path)
        try:
            if self.name != "windows":
                temporary.symlink_to(target, target_is_directory=True)
            else:
                shutil.copytree(target, temporary)
            if current.exists() or current.is_symlink():
                current.replace(backup)
            temporary.replace(current)
            if backup.exists() or backup.is_symlink():
                backup.unlink() if backup.is_symlink() or backup.is_file() else shutil.rmtree(backup)
        except Exception:
            # The fixed pointer was already changed; restore it if the compatibility switch fails.
            if previous and (root / "versions" / previous).is_dir():
                rollback_payload = {
                    "schema_version": "reasonscript-current-installation/1.0",
                    "active_version": previous,
                    "previous_version": version,
                    "activation_status": "active",
                }
                self.atomic_json_write(root / "metadata/current.json", rollback_payload)
            if backup.exists() or backup.is_symlink():
                if current.exists() or current.is_symlink():
                    current.unlink() if current.is_symlink() or current.is_file() else shutil.rmtree(current)
                backup.replace(current)
            raise

    def restore_version(self, root: Path, version: str, attempted: str | None) -> None:
        self.activate_version(root, version, attempted)


def current_adapter() -> PlatformAdapter:
    return PlatformAdapter(platform_id(), architecture_id())


def adapter_for(name: str, architecture: str) -> PlatformAdapter:
    if name not in {"macos", "linux", "windows"}:
        raise ValueError(f"unsupported platform: {name}")
    return PlatformAdapter(name, architecture)
