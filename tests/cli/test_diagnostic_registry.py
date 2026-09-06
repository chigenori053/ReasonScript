"""Unit tests for DiagnosticRegistry (Issue #43, RS-DXLI-01).

Verifies:
1. Canonical error code hierarchy across 10 categories (CLI, SRC, PRJ, LEX, PAR, NAM, TYP, BLD, RUN, ICE).
2. DiagnosticDefinition structure and field completeness.
3. DiagnosticRegistry lookup, alias resolution, and catalog enumeration.
4. Registry validation detecting duplicates, invalid severities, and unknown categories.
5. Automatic title and help resolution in diagnostic_from_parts.
"""

from __future__ import annotations

import unittest

from toolchain.diagnostics import (
    DEFAULT_REGISTRY,
    DiagnosticDefinition,
    DiagnosticRegistry,
    diagnostic_from_parts,
    validate_diagnostic_registry,
)


class TestDiagnosticRegistry(unittest.TestCase):
    def test_all_10_categories_represented(self) -> None:
        expected_categories = {
            "CLI",
            "Source",
            "Project",
            "Lexer",
            "Parser",
            "Namespace",
            "Type",
            "Build",
            "Runtime",
            "ICE",
        }
        actual_categories = {d.category for d in DEFAULT_REGISTRY.all_definitions()}
        self.assertTrue(
            expected_categories.issubset(actual_categories),
            f"Missing categories: {expected_categories - actual_categories}",
        )

    def test_all_10_prefixes_represented(self) -> None:
        expected_prefixes = {
            "CLI",
            "SRC",
            "PRJ",
            "LEX",
            "PAR",
            "NAM",
            "TYP",
            "BLD",
            "RUN",
            "ICE",
        }
        actual_prefixes = {d.code.split("-", 1)[0] for d in DEFAULT_REGISTRY.all_definitions()}
        self.assertTrue(
            expected_prefixes.issubset(actual_prefixes),
            f"Missing prefixes: {expected_prefixes - actual_prefixes}",
        )

    def test_lookup_by_canonical_code(self) -> None:
        defn = DEFAULT_REGISTRY.get("PAR-0001")
        self.assertIsNotNone(defn)
        assert defn is not None
        self.assertEqual(defn.code, "PAR-0001")
        self.assertEqual(defn.category, "Parser")
        self.assertEqual(defn.severity, "ERROR")
        self.assertTrue(len(defn.title) > 0)
        self.assertTrue(len(defn.default_help) > 0)

    def test_lookup_by_legacy_alias(self) -> None:
        # PV-4 -> NAM-0002
        defn = DEFAULT_REGISTRY.get("PV-4")
        self.assertIsNotNone(defn)
        assert defn is not None
        self.assertEqual(defn.code, "NAM-0002")
        self.assertEqual(DEFAULT_REGISTRY.canonical_code("PV-4"), "NAM-0002")

        # FN-005 -> TYP-0002
        defn2 = DEFAULT_REGISTRY.get("FN-005")
        self.assertIsNotNone(defn2)
        assert defn2 is not None
        self.assertEqual(defn2.code, "TYP-0002")
        self.assertEqual(DEFAULT_REGISTRY.canonical_code("FN-005"), "TYP-0002")

        # LL-002-RESERVED-TOP-LEVEL-CONSTRUCT -> PAR-0002
        defn3 = DEFAULT_REGISTRY.get("LL-002-RESERVED-TOP-LEVEL-CONSTRUCT")
        self.assertIsNotNone(defn3)
        assert defn3 is not None
        self.assertEqual(defn3.code, "PAR-0002")

    def test_registry_self_validation_passes(self) -> None:
        issues = DEFAULT_REGISTRY.validate()
        self.assertEqual(issues, [], f"Registry validation failed: {issues}")

        # validate_diagnostic_registry without args validates default registry codes
        doc_issues = validate_diagnostic_registry()
        self.assertEqual(doc_issues, [], f"Diagnostic document issues: {doc_issues}")

    def test_custom_registry_validation_catches_invalid_codes(self) -> None:
        reg = DiagnosticRegistry()
        reg.register(DiagnosticDefinition(
            code="INVALIDCODE", category="Parser", severity="ERROR",
        ))
        reg.register(DiagnosticDefinition(
            code="PAR-9999", category="InvalidCat", severity="ERROR",
        ))
        reg.register(DiagnosticDefinition(
            code="PAR-9998", category="Parser", severity="INVALID_SEV",
        ))
        issues = reg.validate()
        issue_codes = {diag.code for diag in issues}
        self.assertIn("DG-009", issue_codes)  # Unknown code pattern
        self.assertIn("DG-005", issue_codes)  # Invalid category
        self.assertIn("DG-003", issue_codes)  # Invalid severity

    def test_automatic_metadata_population_in_diagnostic_from_parts(self) -> None:
        # Title and help omitted, should be populated from DEFAULT_REGISTRY
        diag = diagnostic_from_parts(
            code="LEX-0001",
            message="unsupported character '?' at 1:1",
            file="test.rsn",
        )
        self.assertEqual(diag.category, "Lexer")
        self.assertEqual(diag.title, "Lexical error")
        self.assertTrue(len(diag.help) > 0)

        # Explicit title and help should take precedence
        diag_custom = diagnostic_from_parts(
            code="LEX-0001",
            message="unsupported character '?' at 1:1",
            file="test.rsn",
            title="Custom Title",
            help="Custom Help",
        )
        self.assertEqual(diag_custom.title, "Custom Title")
        self.assertEqual(diag_custom.help, "Custom Help")


if __name__ == "__main__":
    unittest.main()
