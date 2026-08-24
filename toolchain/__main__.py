"""reason CLI entry point — invoked as `python -m toolchain` or via the `reason` script."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] in {"--version", "-V"}:
        from toolchain.install_foundation import version_command
        return version_command(args[1:])
    if args and args[0] in {"--help", "-h", "help"}:
        _usage()
        return 0
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

    if command == "update":
        from toolchain.install_update.cli import run
        return run(args[1:])

    if command == "install-foundation-report":
        from toolchain.install_update.report import run
        return run(args[1:], Path.cwd())

    if command == "version-validate":
        from toolchain.version_validation import command as version_validate_command
        return version_validate_command(args[1:], Path.cwd())

    project_root = Path.cwd()
    package = _package_arg(args[1:])

    if command in {"check", "run"} and _source_file_arg(args[1:]) is not None:
        source_arg = _source_file_arg(args[1:])
        source_path = Path(source_arg) if source_arg is not None else None
        if command == "run" and source_path is not None:
            try:
                from toolchain.reason_object_graph.language import is_graph_operation_source
                if source_path.suffix == ".rsn" and is_graph_operation_source(source_path.read_text(encoding="utf-8")):
                    from toolchain.reason_object_graph_cmd import run
                    return run(["source-run", *args[1:]], project_root)
            except OSError:
                pass
            package_root = _package_root_for_source(source_path, project_root)
            if package_root is not None and _requires_package_run(
                package_root,
                source_path,
                entry=_option_arg(args[1:], "--entry"),
            ):
                from toolchain.run_cmd import run

                return run(
                    package_root,
                    entry=_option_arg(args[1:], "--entry"),
                    include_trace="--trace" in args[1:],
                    filesystem_read="--allow-read" in args[1:],
                    filesystem_write="--allow-write" in args[1:],
                )
        from scripts.reason_cli import main as reason_main
        return reason_main(args)

    if command == "view":
        from toolchain.code_viewer_cmd import run
        return run(args[1:], project_root)

    if command == "build":
        from toolchain.build_cmd import run
        return run(project_root, package=package)

    if command == "run":
        from toolchain.run_cmd import run
        return run(
            project_root,
            package=package,
            entry=_option_arg(args[1:], "--entry"),
            include_trace="--trace" in args[1:],
            filesystem_read="--allow-read" in args[1:],
            filesystem_write="--allow-write" in args[1:],
        )

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
        try:
            from toolchain.ci_cmd import run
        except ModuleNotFoundError as error:
            print(_missing_dependency_message(error), file=sys.stderr)
            return 1
        return run(command, args[1:], project_root)

    if command == "ci-entry":
        from toolchain.ci_entry_cmd import run
        return run(command, args[1:], project_root)

    if command == "tensor-manifest":
        from toolchain.tensor_manifest_cmd import run
        return run(command, args[1:], project_root)

    if command == "computation-ir":
        from toolchain.computation_ir_cmd import run
        return run(command, args[1:], project_root)

    if command == "project-validate":
        from toolchain.project_validate_cmd import run
        return run(args[1:], project_root)

    if command == "phase1r-validate":
        from toolchain.phase1r_validation_cmd import run
        return run(args[1:], project_root)

    if command == "reasonunit-baseline":
        from toolchain.reasonunit_baseline_cmd import run
        return run(args[1:], project_root)

    if command == "reasonunit-compatibility":
        from toolchain.reasonunit_compatibility_cmd import run
        return run(args[1:], project_root)

    if command == "reasonunit-object":
        from toolchain.reasonunit_object_cmd import run
        return run(args[1:], project_root)

    if command == "reason-object-graph":
        from toolchain.reason_object_graph_cmd import run
        return run(args[1:], project_root)

    if command == "reasonunit-file":
        from toolchain.reasonunit_file_cmd import run
        return run(args[1:], project_root)

    if command == "reasonunit-tensor":
        from toolchain.reasonunit_tensor_cmd import run
        return run(args[1:], project_root)

    if command == "tensor":
        from toolchain.tensor_cmd import run
        return run(args[1:], project_root)

    if command == "reasonunit-runtime":
        from toolchain.reasonunit_runtime_cmd import run
        return run(args[1:], project_root)

    if command == "vision":
        from toolchain.vision_runtime_cmd import run
        return run(args[1:], project_root)

    if command == "visualization":
        from toolchain.visualization_runtime_cmd import run
        return run(args[1:], project_root)

    if command == "object":
        from toolchain.object_cmd import run
        return run(args[1:], project_root)

    if command == "reasoning-model":
        from toolchain.reasoning_model_cmd import run
        return run(command, args[1:], project_root)

    if command == "reasoning-eval":
        from toolchain.reasoning_evaluation_cmd import run
        return run(command, args[1:], project_root)

    if command == "reasoning-runtime":
        from toolchain.reasoning_runtime_cmd import run
        return run(command, args[1:], project_root)

    if command == "cluster":
        from toolchain.cluster_runtime_cmd import run
        return run(command, args[1:], project_root)

    if command == "phase8-golden":
        from toolchain.phase8_golden_cmd import run
        return run(command, args[1:], project_root)

    print(f"Error:\n\nUnknownCommand\n\nUnknown command: {command}")
    _usage()
    return 1


def _missing_dependency_message(error: ModuleNotFoundError) -> str:
    module = error.name or "a required module"
    return (
        f"Error:\n\nMissingDependency\n\n"
        f"`reason ci` could not start because the Python module '{module}' is not "
        f"installed in this interpreter ({sys.executable}).\n\n"
        "`reason ci` requires the development dependencies, not just the runtime\n"
        "package. Install them into the interpreter you invoke `reason` with:\n\n"
        "  python3 -m pip install -r requirements-dev.txt\n\n"
        "If you are running under a sandboxed or isolated interpreter (e.g. an\n"
        "agent runner's own venv), either install requirements-dev.txt into that\n"
        "venv, or invoke `reason` with the project's interpreter instead:\n\n"
        "  /path/to/venv-with-requirements-dev/bin/python -m toolchain ci --json"
    )


def _usage() -> None:
    print("Usage: reason <command> [args]")
    print()
    print("Commands:")
    print("  help          Show this help")
    print("  init <name>   Create a new ReasonScript project")
    print("  doctor        Diagnose the installed environment")
    print("  install-info  Show the installation manifest")
    print("  install-validate Validate the installation contract")
    print("  update         Check, install, validate, inspect, or roll back an update package")
    print("  install-foundation-report Generate Install Foundation validation summary")
    print("  version-validate Validate release version metadata")
    print("  build         Compile source files")
    print("  run           Execute the compiled program")
    print("  test          Run test suites")
    print("  check         Validate sources without building")
    print("  view          Browse .rsn source alongside its compiled representations")
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
    print("  tensor-manifest Emit/check the frozen Tensor function contract manifest")
    print("  computation-ir Lower a .rsn file to reason-computation-ir/0.1 JSON")
    print("  project-validate Validate a standalone ReasonScript project")
    print("  phase1r-validate Generate and validate Phase 1R probes")
    print("  reasonunit-baseline Generate or validate the RUO-C0 compatibility baseline")
    print("  reasonunit-compatibility Generate or validate the RUO-C1 compatibility foundation")
    print("  reasonunit-object Generate or validate the RUO-U1 universal Object model")
    print("  reason-object-graph Generate or validate the MRA Reason Object Graph profile")
    print("  reasonunit-file Read, write, validate, inspect, select, and verify canonical .ruo files")
    print("  reasonunit-tensor Encode, validate, inspect, decode, select, convert, and verify Tensor payloads")
    print("  tensor        Import, inspect, and verify canonical .rstensor files")
    print("  reasonunit-runtime Load, query, revise, project, and validate native ReasonUnit Objects")
    print("  vision        Validate observations and construct RUO/Tensor vision artifacts")
    print("  visualization Project semantic scenes and render deterministic SVG artifacts")
    print("  object        Check, run, inspect, query, transact, select, project, tensor, and save ReasonUnit Objects")
    print("  reasoning-model validate <file> Validate a Reasoning Model artifact")
    print("  reasoning-eval evaluate <file> Evaluate a Reasoning Model artifact")
    print("  reasoning-eval validate <file> Validate a Reasoning Evaluation Report")
    print("  reasoning-runtime run <source.rsn> Generate a Reasoning Runtime Result")
    print("  cluster       Plan, run, simulate, validate, and compare cluster execution")
    print("  phase8-golden validate Run Phase 8 golden validation")


def _package_arg(args: list[str]) -> str | None:
    if "--package" not in args:
        return None
    index = args.index("--package")
    if index + 1 >= len(args):
        return None
    return args[index + 1]


def _option_arg(args: list[str], option: str) -> str | None:
    if option not in args:
        return None
    index = args.index(option)
    return args[index + 1] if index + 1 < len(args) else None


def _source_file_arg(args: list[str]) -> str | None:
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in {
            "--compiler-mode",
            "--entry",
            "--out",
            "--package",
            "--result-output",
        }:
            skip_next = True
            continue
        if arg.startswith("--"):
            continue
        return arg if arg.endswith(".rsn") else None
    return None


def _package_root_for_source(source_path: Path, cwd: Path) -> Path | None:
    resolved = source_path if source_path.is_absolute() else cwd / source_path
    if not resolved.is_file():
        return None
    for candidate in (resolved.parent, *resolved.parents):
        if (candidate / "reason.toml").is_file():
            return candidate
    return None


def _requires_package_run(
    package_root: Path, source_path: Path, *, entry: str | None
) -> bool:
    """Keep standalone source behavior unless project context is required."""
    if entry is not None:
        return True
    source_dir = package_root / "src"
    if source_dir.is_dir() and sum(1 for _ in source_dir.rglob("*.rsn")) > 1:
        return True
    resolved = source_path if source_path.is_absolute() else Path.cwd() / source_path
    try:
        return any(
            line.lstrip().startswith("import ")
            for line in resolved.read_text(encoding="utf-8").splitlines()
        )
    except OSError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
