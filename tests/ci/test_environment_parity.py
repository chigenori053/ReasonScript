"""CI Test Consistency / Environment Parity v0.1: the test plan does not depend on where the
repository is checked out or on what the developer machine happens to have installed."""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import pytest

from scripts import test_environment as env
from scripts import test_platform, test_report

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
CI = {"CI": "true"}


def _markers(path: Path) -> Path:
    for marker in env.REPO_MARKERS:
        (path / marker).mkdir(parents=True)
    return path


# --- repository root (A, B) -------------------------------------------------------------------------


def test_repository_root_is_identified_by_content():
    assert env.find_repo_root() == ROOT and env.is_reasonscript_repo_root(ROOT)


def test_a_renamed_clone_is_a_repository_root(tmp_path):
    clone = _markers(tmp_path / "reasonscript-test-copy")
    nested = clone / "scripts" / "deeper"
    nested.mkdir(parents=True)
    assert env.is_reasonscript_repo_root(clone)
    assert env.find_repo_root(nested) == clone
    assert env.find_repo_root(nested / "some_file.py") == clone


def test_a_directory_missing_a_marker_is_not_a_repository_root(tmp_path):
    for missing in env.REPO_MARKERS:
        partial = tmp_path / f"without-{missing}"
        for marker in env.REPO_MARKERS:
            if marker != missing:
                (partial / marker).mkdir(parents=True)
        assert not env.is_reasonscript_repo_root(partial)
    with pytest.raises(FileNotFoundError):
        env.find_repo_root(tmp_path / "without-frontend")


def test_b_git_worktree_with_another_name_is_a_repository_root(tmp_path):
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("SKIPPED: not a git checkout (source archive); the renamed-clone test covers the same contract")
    worktree = tmp_path / "not-ReasonScript-worktree"
    git = ["git", "-C", str(ROOT)]
    subprocess.run([*git, "worktree", "add", "--detach", "--no-checkout", str(worktree), "HEAD"], check=True, capture_output=True)
    try:
        subprocess.run(
            ["git", "-C", str(worktree), "checkout", "HEAD", "--", "frontend", "toolchain", "scripts", "ReasonRuntime/Cargo.toml"],
            check=True, capture_output=True,
        )
        assert env.is_reasonscript_repo_root(worktree)
        assert env.find_repo_root(worktree / "scripts" / "test_environment.py") == worktree
        assert worktree.name != "ReasonScript"
    finally:
        subprocess.run([*git, "worktree", "remove", "--force", str(worktree)], capture_output=True)
        subprocess.run([*git, "worktree", "prune"], capture_output=True)


def test_no_test_pins_the_checkout_directory_name():
    bridge = (ROOT / "apps/reasonscript-ide/src-tauri/src/compiler_bridge.rs").read_text(encoding="utf-8")
    assert not re.search(r'assert_eq!\(\s*name,\s*"ReasonScript"', bridge)
    assert "repo_root_is_the_reasonscript_repository" in bridge


# --- optional dependency: local skip, CI fail (C, D, E, F) -----------------------------------------------


def test_c_local_without_node_modules_skips_with_the_reason(tmp_path):
    root = _markers(tmp_path / "clone")
    assert env.vscode_dependency_action(root, {}) == ("skip", env.SKIP_VSCODE_DEPENDENCIES)
    with pytest.raises(unittest.SkipTest, match="npm ci"):
        env.require_vscode_dependencies(root, {})
    assert "SKIPPED: vscode-extension/node_modules not found." in env.SKIP_VSCODE_DEPENDENCIES


def test_d_and_f_with_node_modules_the_tests_run_locally_and_in_ci(tmp_path):
    root = _markers(tmp_path / "clone")
    (root / "vscode-extension" / "node_modules").mkdir(parents=True)
    for environment in ({}, CI):
        assert env.vscode_dependency_action(root, environment) == ("run", "")
        env.require_vscode_dependencies(root, environment)  # neither skips nor fails


def test_e_ci_without_node_modules_fails_and_names_the_fix(tmp_path):
    root = _markers(tmp_path / "clone")
    assert env.vscode_dependency_action(root, CI) == ("fail", env.FAIL_VSCODE_DEPENDENCIES)
    with pytest.raises(AssertionError, match="must run `npm ci` before the Test job"):
        env.require_vscode_dependencies(root, CI)


@pytest.mark.parametrize("value", ["", "0", "false", "False", "no", "off"])
def test_ci_flag_falsey_values_are_not_ci(value):
    assert not env.is_ci({"CI": value}) and not env.is_ci({})


@pytest.mark.parametrize("value", ["1", "true", "True", "yes"])
def test_ci_flag_truthy_values_are_ci(value):
    assert env.is_ci({"CI": value})


def test_the_extension_tests_use_the_shared_helper_not_their_own_checks():
    sources = {
        "tests/lsp/test_vscode_extension_contract.py": "test_vscode_extension_typescript_compiles_cleanly",
        "vscode_extension_phase1_4_tests/test_vscode_extension_phase1_4.py": "test_vsxp14_003_dependency_presence",
    }
    for path, name in sources.items():
        text = (ROOT / path).read_text(encoding="utf-8")
        body = text[text.index(f"def {name}"):]
        assert "test_environment.require_vscode_dependencies()" in body[:400], path
    assert set(sources) == {node.split("::")[0] for node in env.CI_REQUIRED_TESTS.values()}


def test_environment_checks_are_not_scattered_over_the_tests():
    scattered = re.compile(r'environ\.get\(\s*["\']CI["\']|node_modules["\']\)\s*\.exists\(\)')
    offenders = []
    for path in ROOT.rglob("*.py"):
        parts = set(path.relative_to(ROOT).parts)
        if parts & {"node_modules", "target", ".claude", ".git", ".venv", "venv"} or path.name in ("test_environment.py", "test_environment_parity.py"):
            continue
        if scattered.search(path.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


# --- preflight ------------------------------------------------------------------------------------------


def _requirements(vscode_ready: bool):
    return lambda: [
        test_platform.Requirement("Python", True, "3", "", required_locally=True),
        test_platform.Requirement("Rust", True, "cargo", "Rust tests are skipped"),
        test_platform.Requirement(
            "VSCode deps", vscode_ready, "vscode-extension/node_modules",
            "VS Code extension tests are skipped; run `npm ci --prefix vscode-extension`"),
    ]


def test_preflight_local_reports_optional_missing_without_failing(monkeypatch):
    monkeypatch.setattr(test_platform, "preflight_requirements", _requirements(False))
    out = io.StringIO()
    assert test_platform.preflight(ci=False, out=out) == 0
    text = out.getvalue()
    assert "Python       READY" in text and "VSCode deps  MISSING (local optional" in text and "npm ci --prefix" in text


def test_preflight_ci_fails_before_any_test_when_a_dependency_is_missing(monkeypatch):
    monkeypatch.setattr(test_platform, "preflight_requirements", _requirements(False))
    out = io.StringIO()
    assert test_platform.preflight(ci=True, out=out) == 1
    assert "VSCode deps  MISSING (required in CI)" in out.getvalue() and "Preflight FAILED" in out.getvalue()


def test_preflight_passes_when_everything_is_ready(monkeypatch):
    monkeypatch.setattr(test_platform, "preflight_requirements", _requirements(True))
    for ci in (False, True):
        assert test_platform.preflight(ci=ci, out=io.StringIO()) == 0


def test_preflight_runs_before_the_environment_dependent_targets():
    assert {"test", "release-check", "integration"} <= set(test_platform.PREFLIGHT_TARGETS)


def test_only_the_full_plan_requires_the_ci_mandatory_groups():
    full = test_platform._steps_for("test", quick=False, passthrough=[])
    pytest_full = next(step for step in full if step.command[1:3] == ["-m", "pytest"])
    assert pytest_full.env["REASONSCRIPT_REQUIRE_MANDATORY"] == "1"
    assert "-p scripts.test_report" in pytest_full.env["PYTEST_ADDOPTS"]
    partial = test_platform._steps_for("integration", quick=False, passthrough=[])
    assert "REASONSCRIPT_REQUIRE_MANDATORY" not in next(s for s in partial if s.name.startswith("pytest")).env
    filtered = test_platform._steps_for("test", quick=False, passthrough=["-k", "x"])
    assert "REASONSCRIPT_REQUIRE_MANDATORY" not in next(s for s in filtered if s.name.startswith("pytest")).env


# --- skip classification and the CI skip guard -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("reason", "kind"),
    [
        (env.SKIP_VSCODE_DEPENDENCIES, "SKIP_OPTIONAL"),
        ("reason-runtime-host binary not built", "SKIP_OPTIONAL"),
        ("optional Matplotlib backend unavailable", "SKIP_OPTIONAL"),
        ("platform does not support test symlinks", "SKIP_PLATFORM"),
        ("directory symlinks are not available", "SKIP_PLATFORM"),
        ("needs a full moon", "SKIP_UNKNOWN"),
    ],
)
def test_skips_are_classified(reason, kind):
    assert test_report.classify_skip(reason) == kind


def _guard(monkeypatch, *, skips=(), executed=(), ci=True, mandatory=True, strict=False):
    state = {"skips": list(skips), "executed": set(executed)}  # never the live plugin state: this runs under it
    for name, value in (
        ("CI", "true" if ci else ""),
        ("REASONSCRIPT_REQUIRE_MANDATORY", "1" if mandatory else ""),
        ("REASONSCRIPT_STRICT_SKIPS", "1" if strict else ""),
    ):
        monkeypatch.setenv(name, value)
    return test_report._problems(state)


def test_ci_guard_fails_when_a_mandatory_group_did_not_execute(monkeypatch):
    errors, _ = _guard(monkeypatch)
    assert len(errors) == len(env.CI_REQUIRED_TESTS) and "vscode-extension-typescript" in errors[0]
    errors, _ = _guard(monkeypatch, executed=env.CI_REQUIRED_TESTS.values())
    assert errors == []


def test_ci_guard_is_silent_outside_ci_and_for_partial_plans(monkeypatch):
    assert _guard(monkeypatch, ci=False) == ([], [])
    assert _guard(monkeypatch, mandatory=False) == ([], [])


def test_ci_guard_rejects_a_dependency_skip_and_warns_about_unclassified_ones(monkeypatch):
    executed = list(env.CI_REQUIRED_TESTS.values())
    dependency = [("t.py::a", env.SKIP_VSCODE_DEPENDENCIES, "SKIP_OPTIONAL")]
    errors, _ = _guard(monkeypatch, skips=dependency, executed=executed)
    assert len(errors) == 1 and "must not skip" in errors[0]
    unknown = [("t.py::b", "needs a full moon", "SKIP_UNKNOWN")]
    errors, warnings = _guard(monkeypatch, skips=unknown, executed=executed)
    assert errors == [] and "unclassified skip in CI" in warnings[0]
    errors, warnings = _guard(monkeypatch, skips=unknown, executed=executed, strict=True)
    assert len(errors) == 1 and warnings == []
    known = [
        ("t.py::c", "platform does not support test symlinks", "SKIP_PLATFORM"),
        ("t.py::d", "reason-runtime-host binary not built", "SKIP_OPTIONAL"),
    ]
    assert _guard(monkeypatch, skips=known, executed=executed) == ([], [])


# --- workflow contract (npm ci before the test job, one canonical entrypoint) ------------------------------------


def _workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("workflow", "command"),
    [
        ("test.yml", "scripts/test_platform.py test"),
        ("ci.yml", "./reason ci"),
        ("release.yml", "scripts/test_platform.py release-check --quick"),
    ],
)
def test_npm_ci_runs_in_the_extension_directory_before_the_test_plan(workflow, command):
    text = _workflow(workflow)
    install = re.search(r"- run: npm ci\n\s+working-directory: vscode-extension", text) or re.search(
        r"name: Install VS Code extension dependencies\n\s+working-directory: vscode-extension\n\s+run: npm ci", text
    )
    assert install, f"{workflow} must run `npm ci` in vscode-extension"
    assert install.start() < text.index(command), f"{workflow}: npm ci must come before `{command}`"
    assert "npm install" not in text


def test_github_actions_do_not_define_their_own_test_list():
    for workflow in ("test.yml", "ci.yml"):
        assert "pytest" not in _workflow(workflow), workflow
