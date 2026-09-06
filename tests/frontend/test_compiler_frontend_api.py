"""Tests for CompilerFrontend API (Issue #42, RS-DXLI-04).

Verifies:
1. In-memory text analysis without saving to disk.
2. Pipeline phases: lexer -> parser -> name_resolution -> type_check -> completed.
3. Diagnostic code, range, severity, and message consistency between CLI and LSP.
4. Panic / Exception isolation returning ICE-0001.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from frontend.compiler_frontend import CompilerFrontend, FrontendRequest
from frontend.lsp.core import ReasonScriptLanguageServer


class TestCompilerFrontendAPI(unittest.TestCase):
    def test_in_memory_valid_source_completed(self) -> None:
        source = """
package demo

model ValidModel {
    fn add(a: int, b: int): int {
        return a + b
    }
}
"""
        req = FrontendRequest(source=source, filename="in_memory.rsn")
        result = CompilerFrontend.analyze(req)
        self.assertTrue(result.ok)
        self.assertEqual(result.diagnostics, ())
        self.assertIsNotNone(result.ast)
        self.assertEqual(result.phase_reached, "completed")

    def test_lexer_error_phase(self) -> None:
        # Invalid character '?' triggers lexer ValueError
        source = "model Demo { ? }"
        req = FrontendRequest(source=source, filename="lexer_err.rsn")
        result = CompilerFrontend.analyze(req)
        self.assertFalse(result.ok)
        self.assertEqual(result.phase_reached, "lexer")
        self.assertEqual(len(result.diagnostics), 1)
        diag = result.diagnostics[0]
        self.assertEqual(diag.code, "LEX-0001")
        self.assertEqual(diag.category, "LEX")
        self.assertEqual(diag.severity, "ERROR")
        self.assertEqual(diag.location.line, 1)
        self.assertIsNotNone(diag.location.column)

    def test_parser_syntax_error_phase(self) -> None:
        # Missing closing parenthesis in function declaration
        source = "model Demo {\nfn broken(\n}"
        req = FrontendRequest(source=source, filename="parser_err.rsn")
        result = CompilerFrontend.analyze(req)
        self.assertFalse(result.ok)
        self.assertEqual(result.phase_reached, "parser")
        self.assertEqual(len(result.diagnostics), 1)
        diag = result.diagnostics[0]
        self.assertEqual(diag.code, "PAR-0001")
        self.assertEqual(diag.category, "PAR")
        self.assertEqual(diag.severity, "ERROR")
        self.assertIsNotNone(diag.location.line)

    def test_parser_reserved_construct_phase(self) -> None:
        # Reserved top-level construct 'world'
        source = "world Demo {}"
        req = FrontendRequest(source=source, filename="reserved.rsn")
        result = CompilerFrontend.analyze(req)
        self.assertFalse(result.ok)
        self.assertEqual(result.phase_reached, "parser")
        self.assertEqual(len(result.diagnostics), 1)
        diag = result.diagnostics[0]
        self.assertEqual(diag.code, "LL-002-RESERVED-TOP-LEVEL-CONSTRUCT")
        self.assertEqual(diag.category, "PAR")

    def test_name_resolution_error_phase(self) -> None:
        # Illegal runtime import target
        source = """
package demo

model Demo {
    import runtime
}
"""
        req = FrontendRequest(source=source, filename="name_err.rsn")
        result = CompilerFrontend.analyze(req)
        self.assertFalse(result.ok)
        self.assertEqual(result.phase_reached, "name_resolution")
        self.assertEqual(len(result.diagnostics), 1)
        diag = result.diagnostics[0]
        self.assertTrue(diag.code.startswith("NAM-"))
        self.assertEqual(diag.category, "NAM")
        self.assertEqual(diag.severity, "ERROR")

    def test_type_validation_error_phase(self) -> None:
        # Return type mismatch: declared int, returns string
        source = """
package demo

model Demo {
    fn bad_type(): int {
        return "hello"
    }
}
"""
        req = FrontendRequest(source=source, filename="type_err.rsn")
        result = CompilerFrontend.analyze(req)
        self.assertFalse(result.ok)
        self.assertEqual(result.phase_reached, "type_check")
        self.assertEqual(len(result.diagnostics), 1)
        diag = result.diagnostics[0]
        self.assertEqual(diag.code, "TYP-0002")
        self.assertEqual(diag.category, "TYP")
        self.assertEqual(diag.severity, "ERROR")

    def test_cli_lsp_diagnostic_parity(self) -> None:
        # Verify that for the same broken source, CLI frontend and LSP produce identical diagnostic properties
        source = "model Broken {\nfn nope(\n}"
        uri = "file:///workspace/broken.rsn"

        # 1. Frontend analyze (CLI path)
        req = FrontendRequest(source=source, filename=uri, uri=uri)
        fe_result = CompilerFrontend.analyze(req)
        self.assertFalse(fe_result.ok)
        fe_diag = fe_result.diagnostics[0]

        # 2. LSP analyze (LSP path)
        server = ReasonScriptLanguageServer()
        server.open_document(uri, source, 1)
        lsp_diags = server.diagnostics(uri)
        self.assertEqual(len(lsp_diags), 1)
        lsp_diag = lsp_diags[0]

        # Check parity: code, range, severity, message
        self.assertEqual(str(lsp_diag.code), fe_diag.code)
        self.assertEqual(lsp_diag.severity.value.upper(), fe_diag.severity)
        self.assertEqual(lsp_diag.location.range.start.line, (fe_diag.location.line or 1) - 1)
        self.assertEqual(lsp_diag.location.range.start.character, (fe_diag.location.column or 1) - 1)
        self.assertEqual(lsp_diag.message, fe_diag.message)

    def test_ice_panic_isolation(self) -> None:
        # Simulate unexpected crash in parser
        source = "model Demo {}"
        req = FrontendRequest(source=source, filename="crash.rsn")
        with patch("frontend.compiler_frontend.parse_unresolved", side_effect=RuntimeError("Unexpected bug")):
            result = CompilerFrontend.analyze(req)
            self.assertFalse(result.ok)
            self.assertEqual(result.phase_reached, "parser")
            self.assertEqual(len(result.diagnostics), 1)
            diag = result.diagnostics[0]
            self.assertEqual(diag.code, "ICE-0001")
            self.assertEqual(diag.category, "ICE")
            self.assertEqual(diag.severity, "ERROR")
            self.assertIn("Internal compiler error", diag.message)
            self.assertIn("Unexpected bug", diag.message)


if __name__ == "__main__":
    unittest.main()
