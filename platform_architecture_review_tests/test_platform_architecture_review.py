from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = ROOT / "docs" / "platform_architecture_review"


REPORTS = {
    "PAR-001": "language_review.md",
    "PAR-002": "runtime_review.md",
    "PAR-003": "execution_architecture_review.md",
    "PAR-004": "toolchain_review.md",
    "PAR-005": "sdk_review.md",
    "PAR-006": "world_model_sdk_review.md",
    "PAR-007": "lsp_review.md",
    "PAR-008": "ide_review.md",
    "PAR-009": "cross_layer_architecture_report.md",
    "PAR-010": "reasoning_trace_proposal.md",
    "PAR-011": "versioning_strategy_report.md",
}


def _text(name: str) -> str:
    return (REVIEW_DIR / name).read_text(encoding="utf-8")


def test_par_001_through_par_011_review_reports_exist_and_are_classified():
    for task, filename in REPORTS.items():
        path = REVIEW_DIR / filename
        assert path.is_file(), task
        text = path.read_text(encoding="utf-8")
        assert "Classification:" in text, task
        assert "Findings" in text or "Review Answers" in text or "Strategy" in text, task


def test_par_012_architecture_classification_covers_all_subsystems():
    text = _text("platform_architecture_v1.md")
    for subsystem in (
        "Language",
        "Runtime",
        "Execution Architecture",
        "Toolchain",
        "SDK",
        "World Model SDK",
        "LSP",
        "IDE",
        "Cross-Layer Architecture",
        "ReasoningTrace",
        "Versioning",
    ):
        assert subsystem in text
    for classification in (
        "Partially Complete",
        "Requires Refactoring",
        "Missing",
    ):
        assert classification in text


def test_par_013_risk_assessment_identifies_platform_risks():
    text = _text("platform_architecture_v1.md")
    for risk in (
        "Trace fragmentation",
        "Diagnostic divergence",
        "Package graph ambiguity",
        "LSP semantic duplication",
        "Runtime capability drift",
    ):
        assert risk in text
    assert "| Risk | Severity | Mitigation |" in text


def test_par_014_beta_readiness_assessment_records_gates():
    text = _text("platform_architecture_v1.md")
    assert "Current state: Not Beta-ready." in text
    for gate in (
        "Platform diagnostics",
        "ReasoningTrace",
        "Toolchain package graph",
        "ExecutionScope and CallStack semantics",
    ):
        assert gate in text


def test_par_015_roadmap_update_references_beta_planning():
    text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
    assert "## Beta Planning" in text
    assert "docs/platform_architecture_review/platform_architecture_v1.md" in text
    assert "Specify `reasoning-trace/0.1`" in text


def test_review_index_maps_all_par_tasks():
    text = _text("README.md")
    for number in range(1, 16):
        assert f"PAR-{number:03d}" in text
    assert "ReasonScript Platform Architecture Review v1.0" in text
    assert "Status: Complete" in text


def test_cross_layer_report_records_integration_risks():
    text = _text("cross_layer_architecture_report.md")
    for item in (
        "Language to Runtime",
        "Runtime to SDK",
        "SDK to World Model SDK",
        "Execution Architecture to Runtime",
        "LSP to Compiler",
        "IDE to Toolchain",
    ):
        assert item in text
    assert "Requires Refactoring" in text


def test_reasoning_trace_proposal_defines_platform_envelope():
    text = _text("reasoning_trace_proposal.md")
    for field in ("trace_id", "source", "events", "evidence", "diagnostics"):
        assert field in text
    assert "reasoning-trace/0.1" in text


def test_versioning_strategy_defines_platform_compatibility_matrix_need():
    text = _text("versioning_strategy_report.md")
    assert "platform-level compatibility matrix" in text
    assert "ReasonScript Platform Architecture v1.0" in text
    assert "schema metadata" in text
