"""Editor-agnostic ReasonScript IDE Integration Phase 1 services."""

from __future__ import annotations

import contextlib
import io
import json
import re
import time
from pathlib import Path
from typing import Callable

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

from frontend.lsp import Diagnostic, DiagnosticSeverity, Location
from frontend.lsp.model import point_range
from toolchain.build_cmd import run as build_run
from toolchain.check_cmd import run as check_run
from toolchain.manifest import Manifest, SUPPORTED_BACKENDS
from toolchain.run_cmd import run as project_run
from toolchain.runner_cmd import run as test_run

from .model import (
    OUTPUT_CHANNELS,
    BuildResult,
    CheckResult,
    CommandName,
    CommandResult,
    CommandStatus,
    IdeConfiguration,
    OutputChannel,
    RunResult,
    SCHEMA,
    TestResult,
    Workspace,
    WorkspaceStatus,
)


ToolchainFunction = Callable[[Path], int]


class WorkspaceNotFoundError(ValueError):
    pass


class ReasonScriptIde:
    """Stable extension surface for IDE Phase 1."""

    schema = SCHEMA
    supported_runtimes = tuple(sorted(SUPPORTED_BACKENDS))
    execution_architecture = (
        "ExecutionCoordinator",
        "ExecutionRequest",
        "ExecutionResult",
        "CallStack",
        "TransactionModel",
    )

    def __init__(self, workspace_root: str | Path | None = None) -> None:
        self.workspace: Workspace | None = None
        self.output_channels = {
            name: OutputChannel(value) for name, value in OUTPUT_CHANNELS.items()
        }
        self.status = WorkspaceStatus(False)
        self.last_result: CommandResult | None = None
        if workspace_root is not None:
            self.load_workspace(workspace_root)

    def detect_workspace(self, start: str | Path) -> Path | None:
        current = Path(start).resolve()
        if current.is_file():
            current = current.parent
        for path in (current, *current.parents):
            if (path / "reason.toml").is_file():
                return path
        return None

    def load_workspace(self, start: str | Path) -> Workspace:
        root = self.detect_workspace(start)
        if root is None:
            raise WorkspaceNotFoundError(f"reason.toml not found from {start}")
        manifest = Manifest.load(root)
        workspace = Workspace(root, _load_ide_configuration(root), manifest.backend)
        self.workspace = workspace
        self.status = WorkspaceStatus(True, runtime_status=manifest.backend)
        return workspace

    def build(self) -> BuildResult:
        result = self._invoke(CommandName.BUILD, build_run)
        files = _compiled_files(result.output)
        build_result = BuildResult(**result.__dict__, files_compiled=files)
        self._record(build_result)
        return build_result

    def run(self) -> RunResult:
        result = self._invoke(CommandName.RUN, project_run)
        execution_result = _json_payload(result.output)
        backend = (
            str(execution_result.get("backend"))
            if isinstance(execution_result, dict) and "backend" in execution_result
            else self._workspace().runtime_backend
        )
        run_result = RunResult(
            **result.__dict__,
            execution_result=execution_result if isinstance(execution_result, dict) else None,
            backend=backend,
        )
        self._record(run_result)
        return run_result

    def test(self) -> TestResult:
        result = self._invoke(CommandName.TEST, test_run)
        passed, failed = _test_counts(result.output)
        test_result = TestResult(
            **result.__dict__,
            total=passed + failed,
            passed=passed,
            failed=failed,
        )
        self._record(test_result)
        return test_result

    def check(self) -> CheckResult:
        result = self._invoke(CommandName.CHECK, check_run)
        check_result = CheckResult(**result.__dict__)
        self._record(check_result)
        return check_result

    def execute_default(self) -> CommandResult:
        command = self._workspace().configuration.default_command
        return self.execute(command)

    def execute(self, command: CommandName | str) -> CommandResult:
        command_name = CommandName(command)
        if command_name == CommandName.BUILD:
            return self.build()
        if command_name == CommandName.RUN:
            return self.run()
        if command_name == CommandName.TEST:
            return self.test()
        return self.check()

    def unified_diagnostics(self) -> tuple[Diagnostic, ...]:
        if self.last_result is None:
            return ()
        return self.last_result.diagnostics

    def _invoke(self, command: CommandName, function: ToolchainFunction) -> CommandResult:
        workspace = self._workspace()
        start = time.perf_counter()
        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                exit_code = function(workspace.root)
        except Exception as error:  # editor crashes are prohibited
            exit_code = 99
            print(f"Error:\n\nIDECommandFailure\n\n{error}", file=stdout)
        duration = time.perf_counter() - start
        output = stdout.getvalue()
        status = CommandStatus.SUCCESS if exit_code == 0 else CommandStatus.FAILED
        return CommandResult(
            command=command,
            status=status,
            exit_code=exit_code,
            diagnostics=_diagnostics_from_output(workspace.root, output),
            duration=duration,
            output=output,
            invocation=("reason", command.value),
        )

    def _record(self, result: CommandResult) -> None:
        self.last_result = result
        self.output_channels[result.command] = OutputChannel(
            OUTPUT_CHANNELS[result.command], result.output
        )
        self.status = _next_status(self.status, result)

    def _workspace(self) -> Workspace:
        if self.workspace is None:
            raise WorkspaceNotFoundError("workspace is not loaded")
        return self.workspace


# Stable extension API aliases.
BuildCommand = ReasonScriptIde.build
RunCommand = ReasonScriptIde.run
TestCommand = ReasonScriptIde.test
CheckCommand = ReasonScriptIde.check


def _load_ide_configuration(root: Path) -> IdeConfiguration:
    data = tomllib.loads((root / "reason.toml").read_text(encoding="utf-8"))
    ide = data.get("ide", {})
    command = CommandName(ide.get("default_command", CommandName.RUN.value))
    return IdeConfiguration(
        default_command=command,
        auto_check=bool(ide.get("auto_check", True)),
        show_execution_trace=bool(ide.get("show_execution_trace", False)),
    )


def _diagnostics_from_output(root: Path, output: str) -> tuple[Diagnostic, ...]:
    if "Error:" not in output:
        return ()
    diagnostics: list[Diagnostic] = []
    chunks = [chunk.strip() for chunk in output.split("Error:") if chunk.strip()]
    for chunk in chunks:
        line = next((item for item in chunk.splitlines() if item.strip()), "ToolchainError")
        file_match = re.search(r"(/[^\s:]+\.rsn):\s*([^:]+):\s*(.+)", chunk)
        if file_match:
            uri = Path(file_match.group(1)).resolve().as_uri()
            code = file_match.group(2).strip()
            message = file_match.group(3).strip()
        else:
            uri = root.resolve().as_uri()
            code = line.strip()
            message = chunk
        diagnostics.append(
            Diagnostic(
                DiagnosticSeverity.ERROR,
                code,
                message,
                Location(uri, point_range(0, 0)),
            )
        )
    return tuple(diagnostics)


def _compiled_files(output: str) -> int:
    match = re.search(r"(\d+)\s+file\(s\)\s+compiled", output)
    return int(match.group(1)) if match else 0


def _test_counts(output: str) -> tuple[int, int]:
    passed_match = re.search(r"(\d+)\s+passed", output)
    failed_match = re.search(r"(\d+)\s+failed", output)
    return (
        int(passed_match.group(1)) if passed_match else 0,
        int(failed_match.group(1)) if failed_match else 0,
    )


def _json_payload(output: str) -> dict[str, object] | None:
    start = output.find("{")
    end = output.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        payload = json.loads(output[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _next_status(status: WorkspaceStatus, result: CommandResult) -> WorkspaceStatus:
    label = {
        (CommandName.BUILD, CommandStatus.SUCCESS): "Build Success",
        (CommandName.BUILD, CommandStatus.FAILED): "Build Failed",
        (CommandName.TEST, CommandStatus.SUCCESS): "Tests Passed",
        (CommandName.TEST, CommandStatus.FAILED): "Tests Failed",
        (CommandName.RUN, CommandStatus.SUCCESS): "ReasonScript Ready",
        (CommandName.RUN, CommandStatus.FAILED): "Run Failed",
        (CommandName.CHECK, CommandStatus.SUCCESS): "ReasonScript Ready",
        (CommandName.CHECK, CommandStatus.FAILED): "Check Failed",
    }[(result.command, result.status)]
    return WorkspaceStatus(
        workspace_loaded=status.workspace_loaded,
        build_status=(
            result.status.value if result.command == CommandName.BUILD else status.build_status
        ),
        test_status=(
            result.status.value if result.command == CommandName.TEST else status.test_status
        ),
        runtime_status=(
            result.status.value if result.command == CommandName.RUN else status.runtime_status
        ),
        status_bar=label,
    )
