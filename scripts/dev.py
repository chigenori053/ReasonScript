#!/usr/bin/env python3
"""ReasonScript IDE — Phase 1 Unified Development Command."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> int:
    target = cwd or REPO_ROOT
    merged_env = {**os.environ, **(env or {})}
    print(f"  $ {' '.join(cmd)}  (in {target.relative_to(REPO_ROOT) if cwd else '.'})")
    result = subprocess.run(cmd, cwd=target, env=merged_env)
    return result.returncode


def cmd_setup() -> int:
    print("=== setup: installing dependencies ===\n")
    rc = 0

    print("[Python]")
    rc |= run(["python3", "-m", "pip", "install", "-r", "requirements-dev.txt"])

    playground_venv = REPO_ROOT / "playground" / ".venv"
    if not playground_venv.exists():
        print("\n[Playground venv]")
        rc |= run(["python3", "-m", "venv", str(playground_venv)])

    print("\n[Playground Python deps]")
    pip = playground_venv / "bin" / "pip"
    rc |= run([str(pip), "install", "-r", "requirements-dev.txt"])

    print("\n[Playground frontend npm]")
    rc |= run(["npm", "install"], cwd=REPO_ROOT / "playground" / "frontend")

    print("\n[Rust deps]")
    for cargo_dir in ["RuntimeReal", "HybridRuntime", "RuntimeComplex"]:
        p = REPO_ROOT / cargo_dir
        if (p / "Cargo.toml").exists():
            rc |= run(["cargo", "fetch"], cwd=p)

    return rc


def cmd_check() -> int:
    print("=== check: environment and repository sanity ===\n")
    rc = run(["python3", "scripts/check_environment.py"])
    return rc


def cmd_playground() -> int:
    print("=== playground: launching Playground IDE ===\n")
    script = REPO_ROOT / "playground" / "start.sh"
    if not script.exists():
        print(f"  [ERROR] {script} not found")
        return 1
    rc = run(["bash", str(script)])
    return rc


def cmd_backend() -> int:
    print("=== backend: launching Playground backend (port 8000) ===\n")
    venv_uvicorn = REPO_ROOT / "playground" / ".venv" / "bin" / "uvicorn"
    uvicorn = str(venv_uvicorn) if venv_uvicorn.exists() else "uvicorn"
    env = {"PYTHONPATH": str(REPO_ROOT)}
    rc = run(
        [uvicorn, "playground.backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        env=env,
    )
    return rc


def cmd_frontend() -> int:
    print("=== frontend: launching Playground frontend dev server (port 5173) ===\n")
    rc = run(["npm", "run", "dev", "--", "--port", "5173"],
             cwd=REPO_ROOT / "playground" / "frontend")
    return rc


def cmd_ide() -> int:
    print("=== ide: Desktop IDE (Tauri) ===\n")
    tauri_dir = REPO_ROOT / "ide" / "desktop"
    if not tauri_dir.exists():
        print("  [INFO] Desktop IDE (ide/desktop) is not present in this repository.")
        print("  [INFO] This component is planned for a future phase.")
        print("  [INFO] Use 'python3 scripts/dev.py playground' to launch the Playground IDE.")
        return 0
    rc = run(["npm", "run", "tauri", "dev"], cwd=tauri_dir)
    return rc


def cmd_build() -> int:
    print("=== build: production / validation build ===\n")
    rc = 0
    print("[Playground frontend build]")
    rc |= run(["npm", "run", "build"], cwd=REPO_ROOT / "playground" / "frontend")
    return rc


def cmd_test(subcmd: str) -> int:
    subcmd = subcmd.lower()

    if subcmd == "smoke":
        print("=== test smoke: minimum validation ===\n")
        rc = 0
        print("[compatibility tests]")
        rc |= run(["python3", "-m", "pytest", "tests/compatibility", "-v", "--tb=short"])
        print("\n[playground integration tests]")
        rc |= run(["python3", "-m", "pytest", "playground_integration_tests", "-v", "--tb=short"])
        print("\n[frontend build]")
        rc |= run(["npm", "run", "build"], cwd=REPO_ROOT / "playground" / "frontend")
        return rc

    if subcmd == "backend":
        print("=== test backend: compiler / analyzer / compatibility ===\n")
        return run([
            "python3", "-m", "pytest",
            "tests/compatibility",
            "playground_integration_tests",
            "tests/playground",
            "-v", "--tb=short",
        ])

    if subcmd == "frontend":
        print("=== test frontend: TypeScript / React build ===\n")
        return run(["npm", "run", "build"], cwd=REPO_ROOT / "playground" / "frontend")

    if subcmd == "rust":
        print("=== test rust: Rust workspace tests ===\n")
        rc = 0
        for cargo_dir in ["RuntimeReal", "HybridRuntime"]:
            p = REPO_ROOT / cargo_dir
            if (p / "Cargo.toml").exists():
                print(f"\n[{cargo_dir}]")
                rc |= run(["cargo", "test"], cwd=p)
        return rc

    if subcmd == "ide":
        print("=== test ide: IDE contract / visualization ===\n")
        return run([
            "python3", "-m", "pytest",
            "ide_phase1_tests",
            "tests/ide",
            "-v", "--tb=short",
        ])

    if subcmd == "all":
        print("=== test all: CI-equivalent validation ===\n")
        rc = 0
        for sub in ["backend", "frontend", "rust", "ide"]:
            rc |= cmd_test(sub)
        return rc

    print(f"  [ERROR] Unknown test subcmd: {subcmd}")
    print("  Available: smoke | backend | frontend | rust | ide | all")
    return 1


USAGE = """\
Usage: python3 scripts/dev.py <command>

Commands:
  setup          Install / fetch all dependencies
  check          Environment and repository sanity check
  playground     Launch Playground IDE (backend + frontend)
  ide            Launch Desktop IDE (Tauri)
  backend        Launch Playground backend only (port 8000)
  frontend       Launch Playground frontend only (port 5173)
  build          Production / validation build
  test smoke     Minimum smoke validation
  test backend   Compiler / analyzer / compatibility tests
  test frontend  Frontend build validation
  test rust      Rust workspace tests
  test ide       IDE contract / visualization tests
  test all       CI-equivalent full test run
"""


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(USAGE)
        return 1

    cmd = args[0]

    if cmd == "setup":
        return cmd_setup()
    if cmd == "check":
        return cmd_check()
    if cmd == "playground":
        return cmd_playground()
    if cmd == "ide":
        return cmd_ide()
    if cmd == "backend":
        return cmd_backend()
    if cmd == "frontend":
        return cmd_frontend()
    if cmd == "build":
        return cmd_build()
    if cmd == "test":
        if len(args) < 2:
            print("  [ERROR] 'test' requires a subcmd: smoke | backend | frontend | rust | ide | all")
            return 1
        return cmd_test(args[1])

    print(f"  [ERROR] Unknown command: {cmd}\n")
    print(USAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
