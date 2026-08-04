"""Phase 4.5-D legacy Playground physical removal contract tests."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_PY = REPO_ROOT / "scripts" / "dev.py"
OFFICIAL_UI = REPO_ROOT / "apps" / "reasonscript-ide" / "ui"
COMMANDS_DOC = REPO_ROOT / "docs" / "development" / "commands.md"
TEST_MATRIX_DOC = REPO_ROOT / "docs" / "development" / "test_matrix.md"
MIGRATION_DOC = REPO_ROOT / "docs" / "development" / "legacy_feature_migration_decision.md"
PLACEMENT_DOC = REPO_ROOT / "docs" / "development" / "legacy_feature_official_ide_placement.md"
CHANGELOG = REPO_ROOT / "docs" / "changelog" / "ide_phase_4_5_d_legacy_playground_physical_removal.md"
REMOVAL_DOC = REPO_ROOT / "docs" / "development" / "legacy_playground_physical_removal_phase_4_5_d.md"

ALLOWED_HISTORICAL_FILES = {
    REPO_ROOT / "docs" / "development" / "legacy_playground_removal_impact.md",
    REPO_ROOT / "docs" / "development" / "ide_code_review_phase_4_5_a.md",
    REPO_ROOT / "docs" / "development" / "ide_version_inventory.md",
    REMOVAL_DOC,
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_playground_frontend_directory_does_not_exist() -> None:
    assert not (REPO_ROOT / "playground" / "frontend").exists()


def test_playground_backend_directory_exists() -> None:
    assert (REPO_ROOT / "playground" / "backend").is_dir()


def test_frontend_python_package_exists() -> None:
    assert (REPO_ROOT / "frontend").is_dir()
    assert (REPO_ROOT / "frontend" / "__init__.py").is_file()


def test_official_ide_ui_exists() -> None:
    assert OFFICIAL_UI.is_dir()
    assert (OFFICIAL_UI / "package.json").is_file()


def test_dev_py_does_not_depend_on_playground_frontend() -> None:
    source = _read(DEV_PY)
    assert "playground/frontend" not in source
    assert '"playground" / "frontend"' not in source
    assert "playground\" / \"frontend\"" not in source


def test_dev_py_has_no_active_legacy_frontend_command() -> None:
    source = _read(DEV_PY)
    assert "def cmd_playground()" not in source
    assert "def cmd_frontend()" not in source
    assert 'if cmd == "playground":\n        return cmd_playground()' not in source
    assert 'if cmd == "frontend":\n        return cmd_frontend()' not in source
    assert "playground-frontend" not in source
    assert "playground-legacy" not in source


def test_dev_py_test_frontend_targets_official_ide_ui() -> None:
    source = _read(DEV_PY)
    marker = 'if subcmd == "frontend":'
    start = source.index(marker)
    end = source.index('if subcmd == "rust":')
    block = source[start:end]
    assert "Official IDE UI build" in block
    assert '"apps" / "reasonscript-ide" / "ui"' in block


def test_dev_py_smoke_does_not_build_legacy_frontend() -> None:
    source = _read(DEV_PY)
    start = source.index('if subcmd == "smoke":')
    end = source.index('if subcmd == "backend":')
    smoke_block = source[start:end]
    assert '"playground" / "frontend"' not in smoke_block
    assert "playground/frontend" not in smoke_block


def test_active_docs_do_not_instruct_legacy_frontend() -> None:
    for doc in [COMMANDS_DOC, TEST_MATRIX_DOC]:
        source = _read(doc)
        assert "playground-frontend" not in source
        assert "npm run build` in `playground/frontend" not in source
        assert "npm run dev -- --port 5173` in `playground/frontend" not in source
        assert "playground/frontend/ →" not in source


def test_official_ide_ui_path_remains_apps_reasonscript_ide_ui() -> None:
    source = _read(COMMANDS_DOC)
    assert "apps/reasonscript-ide/ui" in source
    source = _read(TEST_MATRIX_DOC)
    assert "apps/reasonscript-ide/ui/" in source


def test_historical_docs_may_mention_removed_legacy_ui() -> None:
    for path in ALLOWED_HISTORICAL_FILES:
        if path.is_file():
            source = _read(path)
            assert "playground/frontend" in source or "removed" in source.lower()


def test_deletion_gate_docs_updated() -> None:
    source = _read(MIGRATION_DOC)
    assert "LEGACY PLAYGROUND FRONTEND REMOVED" in source
    source = _read(PLACEMENT_DOC)
    assert "Phase 4.5-D removed the legacy Playground frontend." in source


def test_changelog_exists() -> None:
    assert CHANGELOG.is_file()
    source = _read(CHANGELOG)
    assert "Phase 4.5-D" in source
    assert "Legacy Playground Physical Removal" in source


def test_removal_spec_doc_exists() -> None:
    assert REMOVAL_DOC.is_file()
    source = _read(REMOVAL_DOC)
    assert "playground/frontend" in source
