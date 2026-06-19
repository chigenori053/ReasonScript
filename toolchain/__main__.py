"""reason CLI entry point — invoked as `python -m toolchain` or via the `reason` script."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    if not args:
        _usage()
        return 1

    command = args[0]

    if command == "init":
        if len(args) < 2:
            print("Usage: reason init <project_name>")
            return 1
        from toolchain.init_cmd import run
        return run(args[1])

    project_root = Path.cwd()

    if command == "build":
        from toolchain.build_cmd import run
        return run(project_root)

    if command == "run":
        from toolchain.run_cmd import run
        return run(project_root)

    if command == "test":
        from toolchain.runner_cmd import run
        return run(project_root)

    if command == "check":
        from toolchain.check_cmd import run
        return run(project_root)

    print(f"Error:\n\nUnknownCommand\n\nUnknown command: {command}")
    _usage()
    return 1


def _usage() -> None:
    print("Usage: reason <command> [args]")
    print()
    print("Commands:")
    print("  init <name>   Create a new ReasonScript project")
    print("  build         Compile source files")
    print("  run           Execute the compiled program")
    print("  test          Run test suites")
    print("  check         Validate sources without building")


if __name__ == "__main__":
    raise SystemExit(main())
