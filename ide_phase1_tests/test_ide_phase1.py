from __future__ import annotations

from pathlib import Path

from frontend.ide import (
    SCHEMA,
    BuildResult,
    CheckResult,
    CommandName,
    CommandStatus,
    ReasonScriptIde,
    RunResult,
    TestResult,
)


MAIN_RSN = """package hello_world
module main {
fn run(goal) {
return goal
}
}
"""


TEST_RSN = """package hello_world
module sample_test {
fn test(goal) {
return goal
}
}
"""


REASON_TOML = """[package]
name = "hello_world"
version = "0.1.0"

[compiler]
language_core = "0.7"
platform = "0.2"

[runtime]
backend = "RuntimeReal"

[ide]
default_command = "check"
auto_check = true
show_execution_trace = false
"""


def _project(root: Path, *, backend: str = "RuntimeReal", tests: bool = True) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "target" / "ast").mkdir(parents=True)
    (root / "target" / "ir").mkdir()
    (root / "target" / "metadata").mkdir()
    (root / "target" / "runtime").mkdir()
    (root / "packages").mkdir()
    (root / "reason.toml").write_text(REASON_TOML.replace("RuntimeReal", backend), encoding="utf-8")
    (root / "src" / "main.rsn").write_text(MAIN_RSN, encoding="utf-8")
    if tests:
        (root / "tests" / "sample_test.rsn").write_text(TEST_RSN, encoding="utf-8")
    return root


def test_ide1_001_workspace_detection(tmp_path: Path):
    root = _project(tmp_path / "app")
    nested = root / "src"
    ide = ReasonScriptIde()
    assert ide.schema == SCHEMA == "reasonscript-ide/0.1"
    assert ide.detect_workspace(nested) == root
    workspace = ide.load_workspace(nested)
    assert workspace.root == root
    assert ide.status.workspace_loaded


def test_ide1_002_build_command(tmp_path: Path):
    ide = ReasonScriptIde(_project(tmp_path / "app"))
    result = ide.build()
    assert isinstance(result, BuildResult)
    assert result.invocation == ("reason", "build")
    assert result.status == CommandStatus.SUCCESS
    assert result.files_compiled == 1


def test_ide1_003_build_diagnostics(tmp_path: Path):
    root = _project(tmp_path / "app")
    (root / "src" / "bad.rsn").write_text("@@invalid@@", encoding="utf-8")
    result = ReasonScriptIde(root).build()
    assert result.status == CommandStatus.FAILED
    assert result.diagnostics
    assert ReasonScriptIde(root).detect_workspace(root) == root


def test_ide1_004_run_command(tmp_path: Path):
    ide = ReasonScriptIde(_project(tmp_path / "app"))
    ide.build()
    result = ide.run()
    assert isinstance(result, RunResult)
    assert result.invocation == ("reason", "run")
    assert result.status == CommandStatus.SUCCESS


def test_ide1_005_run_result(tmp_path: Path):
    ide = ReasonScriptIde(_project(tmp_path / "app"))
    ide.build()
    result = ide.run()
    assert result.execution_result is not None
    assert result.execution_result["status"] == "success"
    assert result.backend == "RuntimeReal"


def test_ide1_006_test_command(tmp_path: Path):
    ide = ReasonScriptIde(_project(tmp_path / "app"))
    result = ide.test()
    assert isinstance(result, TestResult)
    assert result.invocation == ("reason", "test")


def test_ide1_007_test_result(tmp_path: Path):
    result = ReasonScriptIde(_project(tmp_path / "app")).test()
    assert result.status == CommandStatus.SUCCESS
    assert result.total == 1
    assert result.passed == 1
    assert result.failed == 0


def test_ide1_008_check_command(tmp_path: Path):
    result = ReasonScriptIde(_project(tmp_path / "app")).check()
    assert isinstance(result, CheckResult)
    assert result.invocation == ("reason", "check")


def test_ide1_009_check_result(tmp_path: Path):
    result = ReasonScriptIde(_project(tmp_path / "app")).check()
    assert result.status == CommandStatus.SUCCESS
    assert result.diagnostics == ()
    assert result.duration >= 0


def test_ide1_010_output_channels(tmp_path: Path):
    ide = ReasonScriptIde(_project(tmp_path / "app"))
    ide.build()
    ide.run()
    ide.test()
    ide.check()
    assert ide.output_channels[CommandName.BUILD].name == "ReasonScript Build"
    assert ide.output_channels[CommandName.RUN].name == "ReasonScript Run"
    assert ide.output_channels[CommandName.TEST].name == "ReasonScript Test"
    assert ide.output_channels[CommandName.CHECK].name == "ReasonScript Check"


def test_ide1_011_diagnostic_integration(tmp_path: Path):
    root = _project(tmp_path / "app")
    (root / "src" / "bad.rsn").write_text("@@invalid@@", encoding="utf-8")
    ide = ReasonScriptIde(root)
    result = ide.check()
    assert result.diagnostics
    assert ide.unified_diagnostics() == result.diagnostics


def test_ide1_012_runtime_real_support(tmp_path: Path):
    ide = ReasonScriptIde(_project(tmp_path / "app", backend="RuntimeReal"))
    assert "RuntimeReal" in ide.supported_runtimes
    assert ide.workspace is not None
    assert ide.workspace.runtime_backend == "RuntimeReal"


def test_ide1_013_hybrid_runtime_support(tmp_path: Path):
    ide = ReasonScriptIde(_project(tmp_path / "app", backend="HybridRuntime"))
    assert "HybridRuntime" in ide.supported_runtimes
    assert ide.workspace is not None
    assert ide.workspace.runtime_backend == "HybridRuntime"


def test_ide1_014_execution_coordinator_compatibility(tmp_path: Path):
    ide = ReasonScriptIde(_project(tmp_path / "app"))
    assert "ExecutionCoordinator" in ide.execution_architecture
    assert "ExecutionRequest" in ide.execution_architecture
    assert "ExecutionResult" in ide.execution_architecture
    assert "CallStack" in ide.execution_architecture
    assert "TransactionModel" in ide.execution_architecture


def test_ide1_015_toolchain_compatibility(tmp_path: Path):
    ide = ReasonScriptIde(_project(tmp_path / "app"))
    assert ide.build().invocation == ("reason", "build")
    assert ide.check().invocation == ("reason", "check")
    assert ide.test().invocation == ("reason", "test")


def test_ide1_016_workspace_configuration(tmp_path: Path):
    ide = ReasonScriptIde(_project(tmp_path / "app"))
    assert ide.workspace is not None
    assert ide.workspace.configuration.default_command == CommandName.CHECK
    assert ide.workspace.configuration.auto_check is True
    assert ide.workspace.configuration.show_execution_trace is False
    assert ide.execute_default().command == CommandName.CHECK


def test_ide1_017_status_bar_updates(tmp_path: Path):
    ide = ReasonScriptIde(_project(tmp_path / "app"))
    assert ide.status.status_bar == "ReasonScript Ready"
    ide.build()
    assert ide.status.status_bar == "Build Success"
    ide.test()
    assert ide.status.status_bar == "Tests Passed"


def test_ide1_018_failure_handling(tmp_path: Path):
    root = _project(tmp_path / "app")
    (root / "src").rename(root / "missing_src")
    result = ReasonScriptIde(root).check()
    assert result.status == CommandStatus.FAILED
    assert result.exit_code != 0
    assert result.diagnostics


def test_ide1_019_structured_results(tmp_path: Path):
    ide = ReasonScriptIde(_project(tmp_path / "app"))
    build = ide.build()
    run = ide.run()
    test = ide.test()
    check = ide.check()
    assert isinstance(build, BuildResult)
    assert isinstance(run, RunResult)
    assert isinstance(test, TestResult)
    assert isinstance(check, CheckResult)


def test_ide1_020_end_to_end_ide_execution(tmp_path: Path):
    ide = ReasonScriptIde(_project(tmp_path / "app"))
    assert ide.check().status == CommandStatus.SUCCESS
    assert ide.build().status == CommandStatus.SUCCESS
    assert ide.run().status == CommandStatus.SUCCESS
    assert ide.test().status == CommandStatus.SUCCESS
