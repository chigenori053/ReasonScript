from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_public_cli_and_contributor_docs_exist() -> None:
    required = [
        "docs/reference/cli.md",
        "CONTRIBUTING.md",
        "AGENTS.md",
    ]
    for relative in required:
        assert (REPO_ROOT / relative).is_file()


def test_core_commands_are_documented() -> None:
    commands = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for snippet in [
        "./reason check <source.rsn>",
        "./reason analyze <source.rsn>",
        "./reason run <source.rsn>",
        "./reason artifacts <source.rsn> --out <directory>",
        "./reason ci --json",
    ]:
        assert snippet in commands
