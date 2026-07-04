"""Phase 4.5-B official IDE command wiring contract tests."""
from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_PY = REPO_ROOT / "scripts" / "dev.py"
COMMANDS_DOC = REPO_ROOT / "docs" / "development" / "commands.md"
TEST_MATRIX_DOC = REPO_ROOT / "docs" / "development" / "test_matrix.md"


def _source() -> str:
    return DEV_PY.read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    source = _source()
    module = ast.parse(source)
    lines = source.splitlines()
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"{name} not found")


def test_scripts_dev_defines_cmd_ide_ui() -> None:
    assert "def cmd_ide_ui() -> int:" in _source()
    assert 'if cmd == "ide-ui":' in _source()


def test_cmd_ide_ui_targets_official_ide_ui() -> None:
    source = _function_source("cmd_ide_ui")
    assert '"apps"' in source
    assert '"reasonscript-ide"' in source
    assert '"ui"' in source
    assert '"npm", "run", "dev"' in source
    assert '"5173"' in source


def test_cmd_ide_is_official_workflow_guidance() -> None:
    source = _function_source("cmd_ide")
    assert "Official ReasonScript IDE" in source
    assert "python3 scripts/dev.py backend" in source
    assert "python3 scripts/dev.py ide-ui" in source
    assert "apps/reasonscript-ide/ui" in source
    assert "ide/desktop" not in source


def test_legacy_playground_commands_are_marked() -> None:
    playground_source = _function_source("cmd_playground")
    frontend_source = _function_source("cmd_frontend")

    assert "LEGACY" in playground_source or "DEPRECATED" in playground_source
    assert "LEGACY" in frontend_source or "DEPRECATED" in frontend_source


def test_test_frontend_targets_official_ide_ui() -> None:
    source = _function_source("cmd_test")
    marker = 'if subcmd == "frontend":'
    start = source.index(marker)
    end = source.index('if subcmd in {"playground-frontend", "playground-legacy"}:')
    frontend_block = source[start:end]

    assert "Official IDE UI build" in frontend_block
    assert '"apps"' in frontend_block
    assert '"reasonscript-ide"' in frontend_block
    assert '"ui"' in frontend_block
    assert '"playground"' not in frontend_block


def test_test_playground_frontend_targets_legacy_frontend() -> None:
    source = _function_source("cmd_test")
    marker = 'if subcmd in {"playground-frontend", "playground-legacy"}:'
    start = source.index(marker)
    end = source.index('if subcmd == "rust":')
    legacy_block = source[start:end]

    assert "Legacy Playground frontend build" in legacy_block
    assert '"playground"' in legacy_block
    assert '"frontend"' in legacy_block


def test_smoke_includes_official_ide_ui_build() -> None:
    source = _function_source("cmd_test")
    start = source.index('if subcmd == "smoke":')
    end = source.index('if subcmd == "backend":')
    smoke_block = source[start:end]

    assert "official IDE UI build" in smoke_block
    assert '"apps"' in smoke_block
    assert '"reasonscript-ide"' in smoke_block
    assert '"ui"' in smoke_block


def test_test_all_includes_official_frontend_build_through_frontend_subcommand() -> None:
    source = _function_source("cmd_test")
    start = source.index('if subcmd == "all":')
    all_block = source[start:]

    assert '["backend", "frontend", "rust", "ide"]' in all_block
    assert "cmd_test(sub)" in all_block


def test_usage_mentions_ide_ui_and_legacy_frontend_test() -> None:
    source = _source()
    assert "ide-ui" in source
    assert "Launch Official IDE UI only" in source
    assert "test playground-frontend" in source


def test_commands_doc_documents_official_ide_workflow() -> None:
    source = COMMANDS_DOC.read_text(encoding="utf-8")

    assert "## Official IDE" in source
    assert "apps/reasonscript-ide/ui" in source
    assert "python3 scripts/dev.py backend" in source
    assert "python3 scripts/dev.py ide-ui" in source
    assert "Legacy Playground UI" in source
    assert "test frontend" in source


def test_test_matrix_doc_documents_official_ide_ui_build() -> None:
    source = TEST_MATRIX_DOC.read_text(encoding="utf-8")

    assert "Official IDE UI build validation" in source
    assert "apps/reasonscript-ide/ui/" in source
    assert "playground/frontend/" in source
    assert "npm run build" in source
    assert "not part of smoke validation" in source
