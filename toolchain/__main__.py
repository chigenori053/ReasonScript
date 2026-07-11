"""reason CLI entry point — invoked as `python -m toolchain` or via the `reason` script."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] in {"--version", "-V"}:
        from toolchain.install_foundation import version_command
        return version_command(args[1:])
    if not args:
        _usage()
        return 1

    command = args[0]

    if command == "init":
        if len(args) < 2:
            print("Usage: reason init <project_name>")
            return 1
        from toolchain.init_cmd import run
        return run(args[1], args[2:])

    if command == "doctor":
        from toolchain.install_foundation import doctor_command
        return doctor_command(args[1:])

    if command == "install-info":
        from toolchain.install_foundation import install_info_command
        return install_info_command(args[1:])

    if command in {"install-validate", "install-ci"}:
        from toolchain.install_foundation import install_validate_command
        return install_validate_command(args[1:])

    project_root = Path.cwd()
    package = _package_arg(args[1:])

    if command in {"check", "run"} and _source_file_arg(args[1:]) is not None:
        from scripts.reason_cli import main as reason_main
        return reason_main(args)

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

    if command in {"workspace", "summary", "index", "scan"}:
        from toolchain.workspace_cmd import run
        return run(command, args[1:], project_root)

    if command in {"analyze", "artifacts", "export", "validate-artifacts", "manifest"}:
        from scripts.reason_cli import main as reason_main
        return reason_main(args)

    if command in {"golden", "test-golden", "golden-summary", "update-golden"}:
        from toolchain.golden_cmd import run
        return run(command, args[1:], project_root)

    if command in {"agent-protocol", "agent-report"}:
        from toolchain.agent_protocol_cmd import run
        return run(command, args[1:], project_root)

    if command == "ci":
        from toolchain.ci_cmd import run
        return run(command, args[1:], project_root)

    if command == "ci-entry":
        from toolchain.ci_entry_cmd import run
        return run(command, args[1:], project_root)

    if command == "reasoning-model":
        from toolchain.reasoning_model_cmd import run
        return run(command, args[1:], project_root)

    if command == "reasoning-eval":
        from toolchain.reasoning_evaluation_cmd import run
        return run(command, args[1:], project_root)

    if command == "reasoning-runtime":
        from toolchain.reasoning_runtime_cmd import run
        return run(command, args[1:], project_root)

    if command == "phase8-golden":
        from toolchain.phase8_golden_cmd import run
        return run(command, args[1:], project_root)

    print(f"Error:\n\nUnknownCommand\n\nUnknown command: {command}")
    _usage()
    return 1


def _usage() -> None:
    print("Usage: reason <command> [args]")
    print()
    print("Commands:")
    print("  init <name>   Create a new ReasonScript project")
    print("  doctor        Diagnose the installed environment")
    print("  install-info  Show the installation manifest")
    print("  install-validate Validate the installation contract")
    print("  build         Compile source files")
    print("  run           Execute the compiled program")
    print("  test          Run test suites")
    print("  check         Validate sources without building")
    print("  workspace     Show workspace foundation summary")
    print("  summary       Show machine-readable project summary")
    print("  index         Generate workspace JSON artifacts")
    print("  scan          Scan workspace files and directories")
    print("  analyze       Analyze a .rsn source file")
    print("  artifacts     Generate canonical source artifacts")
    print("  validate-artifacts Validate generated artifact directory")
    print("  manifest      Show generated artifact manifest")
    print("  golden        Run the Golden Test Corpus")
    print("  test-golden   Run the Golden Test Corpus")
    print("  golden-summary Show Golden Test Corpus summary")
    print("  agent-protocol Validate Agent Development Protocol rules")
    print("  agent-report  Emit Agent Development Protocol report")
    print("  ci            Run the canonical CI Stabilization pipeline")
    print("  ci-entry      Validate the canonical CI entry point contract")
    print("  reasoning-model validate <file> Validate a Reasoning Model artifact")
    print("  reasoning-eval evaluate <file> Evaluate a Reasoning Model artifact")
    print("  reasoning-eval validate <file> Validate a Reasoning Evaluation Report")
    print("  reasoning-runtime run <source.rsn> Generate a Reasoning Runtime Result")
    print("  phase8-golden validate Run Phase 8 golden validation")


def _package_arg(args: list[str]) -> str | None:
    if "--package" not in args:
        return None
    index = args.index("--package")
    if index + 1 >= len(args):
        return None
    return args[index + 1]


def _source_file_arg(args: list[str]) -> str | None:
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in {"--compiler-mode", "--out"}:
            skip_next = True
            continue
        if arg.startswith("--"):
            continue
        return arg if arg.endswith(".rsn") else None
    return None


if __name__ == "__main__":
    raise SystemExit(main())
