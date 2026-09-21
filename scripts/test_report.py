"""pytest plugin for the canonical test plan: skip classification and the CI skip guard.

Loaded by `scripts/test_platform.py` (through `PYTEST_ADDOPTS`). It never changes which
tests run; it only reports, and under CI fails the plan when:

* a CI-required test (`scripts.test_environment.CI_REQUIRED_TESTS`) did not execute; or
* a test skipped because a declared dependency is missing (the `SKIPPED:` reasons from
  `scripts.test_environment`), which under CI must already have failed.

An unclassified skip is a warning under CI (an error with `REASONSCRIPT_STRICT_SKIPS=1`).
The summary avoids the words "N passed" so `./reason ci` does not count it twice.
"""

from __future__ import annotations

import os
import re

from scripts.test_environment import CI_REQUIRED_TESTS, is_ci

PLATFORM = re.compile(r"symlink|platform|windows|win32|macos|darwin|linux|posix", re.IGNORECASE)
OPTIONAL = re.compile(
    r"^SKIPPED:|optional|not installed|is not installed|unavailable|not built|not been built|"
    r"requires development dependencies|Go toolchain",
    re.IGNORECASE,
)

_state: dict = {}


def classify_skip(reason: str) -> str:
    if PLATFORM.search(reason):
        return "SKIP_PLATFORM"
    if OPTIONAL.search(reason):
        return "SKIP_OPTIONAL"
    return "SKIP_UNKNOWN"


def _reset() -> None:
    _state.clear()
    _state.update(passed=0, failed=0, skips=[], executed=set())


def pytest_configure(config) -> None:
    _reset()


def pytest_runtest_logreport(report) -> None:
    if hasattr(report, "context"):  # a subtest report: its test is reported on its own
        return
    if report.when == "call" and report.passed:
        _state["passed"] += 1
        _state["executed"].add(report.nodeid)
    elif report.failed:
        _state["failed"] += 1
    elif report.skipped:
        reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else str(report.longrepr)
        reason = reason.removeprefix("Skipped: ")
        _state["skips"].append((report.nodeid, reason, classify_skip(reason)))


def _problems(state: dict | None = None) -> tuple[list[str], list[str]]:
    """(errors, warnings) of the CI guard; empty outside CI."""
    state = _state if state is None else state
    if not is_ci():
        return [], []
    errors, warnings = [], []
    if os.environ.get("REASONSCRIPT_REQUIRE_MANDATORY"):
        for group, node in CI_REQUIRED_TESTS.items():
            if not any(executed.endswith(node) for executed in state["executed"]):
                errors.append(f"CI-required test group did not execute: {group} ({node})")
    for node, reason, kind in state["skips"]:
        if reason.startswith("SKIPPED:"):
            errors.append(f"CI must not skip on a missing declared dependency: {node}: {reason.splitlines()[0]}")
        elif kind == "SKIP_UNKNOWN":
            line = f"unclassified skip in CI: {node}: {reason}"
            (errors if os.environ.get("REASONSCRIPT_STRICT_SKIPS") else warnings).append(line)
    return errors, warnings


def pytest_sessionfinish(session, exitstatus) -> None:
    errors, _ = _problems()
    if errors and exitstatus == 0:
        session.exitstatus = 1


def pytest_terminal_summary(terminalreporter) -> None:
    skips = _state["skips"]
    counts = {kind: sum(1 for *_, k in skips if k == kind) for kind in ("SKIP_OPTIONAL", "SKIP_PLATFORM", "SKIP_UNKNOWN")}
    write = terminalreporter.write_line
    terminalreporter.section("test plan summary")
    write(f"PASS {_state['passed']}  FAIL {_state['failed']}  " + "  ".join(f"{k} {v}" for k, v in counts.items()))
    for node, reason, kind in skips:
        write(f"  {kind}: {node}: {reason.splitlines()[0] if reason else ''}")
    for group, node in CI_REQUIRED_TESTS.items():
        executed = any(item.endswith(node) for item in _state["executed"])
        write(f"  {group}: {'executed' if executed else 'not executed'}")
    errors, warnings = _problems()
    for line in warnings:
        write(f"WARNING: {line}")
    for line in errors:
        write(f"ERROR: {line}")
