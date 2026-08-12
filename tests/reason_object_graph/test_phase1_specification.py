"""Phase 1 specification guards before the reference model is introduced."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPECIFICATION = ROOT / "docs/specifications/ReasonScript_MRA_RUO_ReasonRelation_Integrated_Model_v0_1.md"
CHANGELOG = ROOT / "docs/changelog/mra_ruo_reasonrelation_integrated_model_phase1.md"


def test_phase1_specification_declares_the_fixed_reference_model_contract() -> None:
    text = SPECIFICATION.read_text(encoding="utf-8")
    for required in (
        "MRA-RUO-RR-IM-0.1",
        "ReasonEntityRef",
        "ReasonGraph",
        "MAX_RELATION_DEPTH",
        "incoming_relation_refs",
        "canonical_coverage",
        "GraphTransaction",
        "SHA-256",
    ):
        assert required in text


def test_phase1_specification_has_the_complete_stable_rri_matrix() -> None:
    text = SPECIFICATION.read_text(encoding="utf-8")
    for number in range(1, 29):
        assert f"RRI-{number:03}" in text
    assert "28/28 RRI tests" in text


def test_phase1_specification_has_a_matching_changelog_entry() -> None:
    assert CHANGELOG.is_file()
    assert "Phase 1" in CHANGELOG.read_text(encoding="utf-8")
