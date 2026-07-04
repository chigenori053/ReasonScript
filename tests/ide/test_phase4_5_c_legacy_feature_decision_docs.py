"""Phase 4.5-C legacy feature decision docs contract tests."""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs" / "development"
CHANGELOG = REPO_ROOT / "docs" / "changelog" / "ide_phase_4_5_c_legacy_feature_decision.md"

FEATURE_DOC = DOCS / "legacy_feature_migration_decision.md"
API_DOC = DOCS / "legacy_api_retention_policy.md"
PLACEMENT_DOC = DOCS / "legacy_feature_official_ide_placement.md"

LEGACY_ONLY_FEATURES = [
    "Audit",
    "Runtime IO output",
    "Input state",
    "Calculation panel",
    "Cycle diagnostics",
    "Runtime trace",
    "Strict diagnostics",
    "Ownership analysis",
    "Type coverage",
    "Exhaustiveness",
    "Determinism",
    "Complexity",
    "Export",
    "Import",
    "Diff",
    "Language audit matrix",
    "Run all",
    "Baseline",
    "Regression runner",
    "Sample selector",
]

LEGACY_ONLY_APIS = [
    "/api/validate",
    "/api/run-all",
    "/api/pipeline",
    "/api/export",
    "/api/import",
    "/api/diff",
    "/api/baseline",
    "/api/language-audit",
    "/api/language-audit/export",
    "/api/examples",
]

DECISION_TERMS = [
    "ALREADY_SUPPORTED",
    "MIGRATE_REQUIRED",
    "MIGRATED",
    "DEPRECATE_ALLOWED",
    "BACKEND_ONLY",
    "DEFERRED",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _table_row_for(source: str, key: str) -> str:
    pattern = re.compile(rf"^\|\s*`?{re.escape(key)}`?\s*\|.*$", re.MULTILINE)
    match = pattern.search(source)
    assert match is not None, key
    return match.group(0)


def _normalized(source: str) -> str:
    return " ".join(source.split())


def test_phase4_5_c_required_docs_exist() -> None:
    for path in [FEATURE_DOC, API_DOC, PLACEMENT_DOC, CHANGELOG]:
        assert path.is_file(), path
        assert path.read_text(encoding="utf-8").strip()


def test_feature_decision_doc_defines_decision_categories() -> None:
    source = _read(FEATURE_DOC)
    assert "## Decision Categories" in source
    for term in DECISION_TERMS:
        assert f"`{term}`" in source


def test_feature_decision_doc_lists_all_legacy_only_features() -> None:
    source = _read(FEATURE_DOC)
    for feature in LEGACY_ONLY_FEATURES:
        assert feature in source


def test_each_legacy_only_feature_has_a_decision() -> None:
    source = _read(FEATURE_DOC)
    for feature in LEGACY_ONLY_FEATURES:
        row = _table_row_for(source, feature)
        assert any(f"`{term}`" in row for term in DECISION_TERMS), row


def test_api_policy_doc_lists_all_legacy_only_apis() -> None:
    source = _read(API_DOC)
    for api in LEGACY_ONLY_APIS:
        assert api in source


def test_each_legacy_only_api_has_a_retention_decision() -> None:
    source = _read(API_DOC)
    allowed_decisions = [
        "KEEP_UNTIL_MIGRATION_DECISION",
        "BACKEND_ONLY",
        "MIGRATE_OR_REMOVE",
        "MIGRATE_REQUIRED",
        "MIGRATE_REQUIRED_OR_BACKEND_ONLY",
        "KEEP_ARTIFACT_OPERATION_API",
        "KEEP_FOR_OFFICIAL_IDE",
        "KEEP_FOR_OFFICIAL_IDE_OR_BACKEND_ONLY",
        "DEFERRED",
    ]
    for api in LEGACY_ONLY_APIS:
        row = _table_row_for(source, api)
        assert any(f"`{decision}`" in row for decision in allowed_decisions), row


def test_placement_doc_preserves_standard_ide_layout() -> None:
    source = _read(PLACEMENT_DOC)
    for tab in ["Overview", "Plan", "Simulation", "Knowledge", "Artifacts"]:
        assert f"`{tab}`" in source
    for tool_window in ["Problems", "Output", "Logs", "Tests"]:
        assert f"`{tool_window}`" in source


def test_placement_doc_does_not_add_new_top_level_right_inspector_tabs() -> None:
    source = _read(PLACEMENT_DOC)
    normalized = _normalized(source)
    assert "does not add new top-level right inspector tabs" in normalized
    assert "Do not add new top-level right inspector tabs" in source
    assert "Allowed top-level right inspector tabs:" in source


def test_deletion_gate_remains_not_closed() -> None:
    source = _read(FEATURE_DOC)
    normalized = _normalized(source)
    assert "NOT CLOSED" in normalized
    assert "ALL LEGACY FEATURE DECISIONS RESOLVED - READY FOR PHYSICAL REMOVAL PLANNING" in source
    assert "Still NOT enough for physical deletion" in source


def test_physical_deletion_is_explicitly_out_of_scope() -> None:
    for path in [FEATURE_DOC, API_DOC, PLACEMENT_DOC, CHANGELOG]:
        source = _read(path)
        assert "physical deletion" in source.lower()
        assert "out of scope" in source.lower()
