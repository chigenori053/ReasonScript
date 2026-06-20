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
    package = _package_arg(args[1:])

    if command == "build":
        from toolchain.build_cmd import run
        return run(project_root, package=package)

    if command == "run":
        from toolchain.run_cmd import run
        return run(project_root, package=package)

    if command == "test":
        from toolchain.runner_cmd import run
        return run(project_root, package=package)

    if command == "check":
        from toolchain.check_cmd import run
        return run(project_root, package=package)

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


def _package_arg(args: list[str]) -> str | None:
    if "--package" not in args:
        return None
    index = args.index("--package")
    if index + 1 >= len(args):
        return None
    return args[index + 1]


if __name__ == "__main__":
    raise SystemExit(main())
