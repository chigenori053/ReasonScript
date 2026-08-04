from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_phase6_required_docs_exist() -> None:
    required = [
        "docs/development/phase6_compiler_runtime_cli_stabilization.md",
        "docs/development/reason_cli_commands.md",
        "docs/development/reason_cli_artifact_policy.md",
        "docs/development/reason_cli_exit_codes.md",
        "docs/development/reason_cli_examples_validation.md",
        "docs/changelog/phase6_compiler_runtime_cli_stabilization.md",
    ]
    for relative in required:
        assert (REPO_ROOT / relative).is_file()


def test_phase6_commands_are_documented() -> None:
    commands = (REPO_ROOT / "docs" / "development" / "commands.md").read_text(encoding="utf-8")
    for snippet in [
        "python3 scripts/dev.py reason check <file.rsn>",
        "python3 scripts/dev.py reason analyze <file.rsn>",
        "python3 scripts/dev.py reason run <file.rsn>",
        "python3 scripts/dev.py reason artifacts <file.rsn> --out <dir>",
        "python3 scripts/dev.py reason examples",
    ]:
        assert snippet in commands

