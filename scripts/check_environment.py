#!/usr/bin/env python3
"""ReasonScript IDE — Phase 1 Environment Check."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_TOOLS = [
    ("python3", ["python3", "--version"]),
    ("pytest",  ["python3", "-m", "pytest", "--version"]),
    ("node",    ["node", "--version"]),
    ("npm",     ["npm", "--version"]),
    ("rustc",   ["rustc", "--version"]),
    ("cargo",   ["cargo", "--version"]),
]

OPTIONAL_TOOLS = [
    ("tauri",   ["cargo", "tauri", "--version"]),
    ("ruff",    ["ruff", "--version"]),
    ("mypy",    ["mypy", "--version"]),
]

REQUIRED_PATHS = [
    "frontend",
    "playground",
    "playground/backend",
    "playground/frontend",
    "tests",
    "docs",
    "scripts",
    "requirements-dev.txt",
]


def _run(cmd: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        out = (result.stdout + result.stderr).strip().splitlines()
        return result.returncode == 0, out[0] if out else ""
    except Exception as exc:
        return False, str(exc)


def check_tools(tools: list[tuple[str, list[str]]], required: bool) -> list[dict]:
    results = []
    for name, cmd in tools:
        ok, version = _run(cmd)
        status = "OK" if ok else ("MISSING" if required else "WARNING")
        results.append({"name": name, "status": status, "version": version})
    return results


def check_paths() -> list[dict]:
    results = []
    for rel in REQUIRED_PATHS:
        p = REPO_ROOT / rel
        ok = p.exists()
        results.append({"path": rel, "status": "OK" if ok else "MISSING"})
    return results


def check_os() -> dict:
    import platform
    system = platform.system()
    ok = system == "Darwin"
    return {"os": system, "status": "OK" if ok else "WARNING", "note": "macOS recommended"}


def main() -> int:
    print("=== ReasonScript Phase 1 Environment Check ===\n")

    required = check_tools(REQUIRED_TOOLS, required=True)
    optional = check_tools(OPTIONAL_TOOLS, required=False)
    paths = check_paths()
    os_info = check_os()

    errors: list[str] = []
    warnings: list[str] = []

    print("[ Required Tools ]")
    for r in required:
        mark = "✓" if r["status"] == "OK" else "✗"
        print(f"  {mark} {r['name']:<12} {r['version']}")
        if r["status"] == "MISSING":
            errors.append(f"Missing required tool: {r['name']}")

    print("\n[ Optional Tools ]")
    for r in optional:
        mark = "✓" if r["status"] == "OK" else "?"
        print(f"  {mark} {r['name']:<12} {r['version'] or 'not found'}")
        if r["status"] == "WARNING":
            warnings.append(f"Optional tool not found: {r['name']}")

    print("\n[ Required Paths ]")
    for p in paths:
        mark = "✓" if p["status"] == "OK" else "✗"
        print(f"  {mark} {p['path']}")
        if p["status"] == "MISSING":
            errors.append(f"Missing path: {p['path']}")

    print("\n[ OS ]")
    mark = "✓" if os_info["status"] == "OK" else "!"
    print(f"  {mark} {os_info['os']}  ({os_info['note']})")
    if os_info["status"] != "OK":
        warnings.append(f"Non-macOS environment: {os_info['os']}")

    print()
    if errors:
        for e in errors:
            print(f"  [ERROR] {e}")
        print(f"\n[FAIL] {len(errors)} error(s) found. Resolve before proceeding.")
        summary = {"status": "FAIL", "errors": errors, "warnings": warnings}
    else:
        if warnings:
            for w in warnings:
                print(f"  [WARN] {w}")
        print("[PASS] Environment check passed.")
        summary = {"status": "PASS", "errors": [], "warnings": warnings}

    print("\n--- machine-readable summary ---")
    print(json.dumps(summary, indent=2))

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
