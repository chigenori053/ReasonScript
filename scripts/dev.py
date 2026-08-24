#!/usr/bin/env python3
"""ReasonScript IDE — Phase 1 Unified Development Command."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> int:
    target = cwd or REPO_ROOT
    merged_env = {**os.environ, **(env or {})}
    print(f"  $ {' '.join(cmd)}  (in {target.relative_to(REPO_ROOT) if cwd else '.'})")
    try:
        result = subprocess.run(cmd, cwd=target, env=merged_env)
    except KeyboardInterrupt:
        print("\n  [INFO] Interrupted by user.")
        return 130
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

    print("\n[Official IDE UI npm]")
    rc |= run(["npm", "install"], cwd=REPO_ROOT / "apps" / "reasonscript-ide" / "ui")

    print("\n[Rust deps]")
    for cargo_dir in ["RuntimeReal", "HybridRuntime"]:
        p = REPO_ROOT / cargo_dir
        if (p / "Cargo.toml").exists():
            rc |= run(["cargo", "fetch"], cwd=p)

    return rc


def cmd_check() -> int:
    print("=== check: environment and repository sanity ===\n")
    rc = run(["python3", "scripts/check_environment.py"])
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


def cmd_ide() -> int:
    print("=== ide: Official ReasonScript IDE ===\n")
    print("Run these in two terminals:\n")
    print("  Terminal 1:")
    print("    python3 scripts/dev.py backend\n")
    print("  Terminal 2:")
    print("    python3 scripts/dev.py ide-ui\n")
    print("Official IDE UI:")
    print("  apps/reasonscript-ide/ui\n")
    print("Backend:")
    print("  playground/backend")
    return 0


def cmd_ide_ui() -> int:
    print("=== ide-ui: launching Official ReasonScript IDE UI (port 5173) ===\n")
    return run(
        ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"],
        cwd=REPO_ROOT / "apps" / "reasonscript-ide" / "ui",
    )


def cmd_build() -> int:
    print("=== build: production / validation build ===\n")
    rc = 0

    print("[Official IDE UI build]")
    rc |= run(["npm", "run", "build"], cwd=REPO_ROOT / "apps" / "reasonscript-ide" / "ui")

    return rc


def cmd_reason(args: list[str]) -> int:
    from scripts.reason_cli import main as reason_main

    return reason_main(args)


def cmd_test(subcmd: str) -> int:
    subcmd = subcmd.lower()

    if subcmd == "smoke":
        print("=== test smoke: minimum validation ===\n")
        rc = 0
        print("[compatibility tests]")
        rc |= run(["python3", "-m", "pytest", "tests/compatibility", "-v", "--tb=short"])
        print("\n[playground integration tests]")
        rc |= run(["python3", "-m", "pytest", "playground_integration_tests", "-v", "--tb=short"])
        print("\n[official IDE UI build]")
        rc |= run(["npm", "run", "build"], cwd=REPO_ROOT / "apps" / "reasonscript-ide" / "ui")
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
        print("=== test frontend: Official IDE UI build ===\n")
        return run(["npm", "run", "build"], cwd=REPO_ROOT / "apps" / "reasonscript-ide" / "ui")

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
  setup                 Install / fetch all dependencies
  check                 Environment and repository sanity check
  ide                   Show Official IDE workflow
  ide-ui                Launch Official IDE UI only (apps/reasonscript-ide/ui, port 5173)
  backend               Launch Playground backend only (port 8000)
  build                 Production / validation build
  reason <subcommand>   ReasonScript CLI: check | analyze | run | artifacts | export | golden | examples
  test smoke            Minimum smoke validation
  test backend          Compiler / analyzer / compatibility tests
  test frontend         Official IDE UI build validation
  test rust             Rust workspace tests
  test ide              IDE contract / visualization tests
  test all              CI-equivalent full test run

Legacy Playground frontend has been removed. Use 'ide' / 'ide-ui' instead.
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
    if cmd == "ide":
        return cmd_ide()
    if cmd == "ide-ui":
        return cmd_ide_ui()
    if cmd == "backend":
        return cmd_backend()
    if cmd == "build":
        return cmd_build()
    if cmd == "reason":
        return cmd_reason(args[1:])
    if cmd == "test":
        if len(args) < 2:
            print("  [ERROR] 'test' requires a subcmd: smoke | backend | frontend | rust | ide | all")
            return 1
        return cmd_test(args[1])
    if cmd in {"playground", "frontend"}:
        print("  [ERROR] Legacy Playground frontend has been removed.")
        print("  Use:")
        print("    python3 scripts/dev.py ide")
        print("    python3 scripts/dev.py ide-ui")
        return 1

    print(f"  [ERROR] Unknown command: {cmd}\n")
    print(USAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
