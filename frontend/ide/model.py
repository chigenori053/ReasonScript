"""ReasonScript IDE Integration Phase 1 data model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from frontend.lsp import Diagnostic


SCHEMA = "reasonscript-ide/0.1"


class CommandName(str, Enum):
    BUILD = "build"
    RUN = "run"
    TEST = "test"
    CHECK = "check"


class CommandStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class IdeConfiguration:
    default_command: CommandName = CommandName.RUN
    auto_check: bool = True
    show_execution_trace: bool = False


@dataclass(frozen=True)
class WorkspaceStatus:
    workspace_loaded: bool
    build_status: str = "NotRun"
    test_status: str = "NotRun"
    runtime_status: str = "NotRun"
    status_bar: str = "ReasonScript Ready"


@dataclass(frozen=True)
class OutputChannel:
    name: str
    content: str = ""


@dataclass(frozen=True)
class CommandResult:
    command: CommandName
    status: CommandStatus
    exit_code: int
    diagnostics: tuple[Diagnostic, ...]
    duration: float
    output: str
    invocation: tuple[str, ...]


@dataclass(frozen=True)
class BuildResult(CommandResult):
    files_compiled: int = 0


@dataclass(frozen=True)
class RunResult(CommandResult):
    execution_result: dict[str, object] | None = None
    backend: str = "RuntimeReal"


@dataclass(frozen=True)
class TestResult(CommandResult):
    total: int = 0
    passed: int = 0
    failed: int = 0


TestResult.__test__ = False


@dataclass(frozen=True)
class CheckResult(CommandResult):
    pass


@dataclass(frozen=True)
class Workspace:
    root: Path
    configuration: IdeConfiguration
    runtime_backend: str


OUTPUT_CHANNELS = {
    CommandName.BUILD: "ReasonScript Build",
    CommandName.RUN: "ReasonScript Run",
    CommandName.TEST: "ReasonScript Test",
    CommandName.CHECK: "ReasonScript Check",
}
