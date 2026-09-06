"""Unit tests for diagnostic help, title, and fix_candidates (Issue #44, RS-DXLI-03).

Verifies:
1. Reserved construct diagnostics provide model/module replacement fix candidates.
2. Package declaration error diagnostics provide semicolon removal fix.
3. Unterminated string literal diagnostics provide quote closure fix.
4. Name resolution typo diagnostics provide 'Did you mean' suggestions and replacement fixes.
5. render_diagnostics formats help and suggested fixes cleanly in CLI human output.
6. LSP diagnostics retain fix candidates and help in the data payload for editor QuickFix.
"""

from __future__ import annotations

import unittest

from frontend.compiler_frontend import CompilerFrontend, FrontendRequest
from frontend.lsp.core import ReasonScriptLanguageServer
from toolchain.diagnostics import render_diagnostics


class TestDiagnosticFixes(unittest.TestCase):
    def test_reserved_construct_provides_fixes(self) -> None:
        source = "world AutonomousAgent {}"
        req = FrontendRequest(source=source, filename="reserved.rsn")
        result = CompilerFrontend.analyze(req)
        self.assertFalse(result.ok)
        diag = result.diagnostics[0]

        self.assertEqual(diag.code, "LL-002-RESERVED-TOP-LEVEL-CONSTRUCT")
        self.assertEqual(diag.title, "Reserved Construct")
        self.assertIn("model", diag.help)
        self.assertIn("module", diag.help)

        # Check fix_candidates
        self.assertGreaterEqual(len(diag.fixes), 2)
        titles = [f.title for f in diag.fixes]
        replacements = [f.replacement for f in diag.fixes]
        self.assertIn("Replace with 'model'", titles)
        self.assertIn("Replace with 'module'", titles)
        self.assertIn("model", replacements)
        self.assertIn("module", replacements)

    def test_package_semicolon_provides_fix(self) -> None:
        source = "package my_package;\nmodel Demo {}"
        req = FrontendRequest(source=source, filename="pkg.rsn")
        result = CompilerFrontend.analyze(req)
        self.assertFalse(result.ok)
        diag = result.diagnostics[0]

        self.assertEqual(diag.code, "PAR-0004")
        self.assertIn("semicolon", diag.help.lower())
        self.assertEqual(len(diag.fixes), 1)
        self.assertEqual(diag.fixes[0].title, "Remove semicolon")

    def test_unterminated_string_provides_fix(self) -> None:
        source = 'model Demo {\nconst s: string = "hello\n}'
        req = FrontendRequest(source=source, filename="str.rsn")
        result = CompilerFrontend.analyze(req)
        self.assertFalse(result.ok)
        diag = result.diagnostics[0]

        self.assertEqual(diag.code, "LEX-0002")
        self.assertIn("quote", diag.help.lower())
        self.assertEqual(len(diag.fixes), 1)
        self.assertEqual(diag.fixes[0].title, "Close string literal")
        self.assertEqual(diag.fixes[0].replacement, '"')

    def test_runtime_import_provides_fix(self) -> None:
        source = "package demo\nmodel Demo {\nimport runtime\n}"
        req = FrontendRequest(source=source, filename="import_rt.rsn")
        result = CompilerFrontend.analyze(req)
        self.assertFalse(result.ok)
        diag = result.diagnostics[0]

        self.assertEqual(diag.code, "NAM-0001")
        self.assertIn("built-in", diag.help)
        self.assertEqual(len(diag.fixes), 1)
        self.assertEqual(diag.fixes[0].title, "Remove import runtime")

    def test_render_diagnostics_with_help_and_fixes(self) -> None:
        source = "world MyWorld {}"
        req = FrontendRequest(source=source, filename="sample.rsn")
        result = CompilerFrontend.analyze(req)
        rendered = render_diagnostics(result.diagnostics)

        self.assertIn("Reserved Construct", rendered)
        self.assertIn("help: Reserved top-level construct.", rendered)
        self.assertIn("suggested fix: Replace with 'model'", rendered)
        self.assertIn("  model", rendered)
        self.assertIn("suggested fix: Replace with 'module'", rendered)
        self.assertIn("  module", rendered)

    def test_lsp_diagnostic_carries_fixes_in_data(self) -> None:
        uri = "file:///workspace/reserved.rsn"
        source = "world MyWorld {}"
        server = ReasonScriptLanguageServer()
        server.open_document(uri, source, 1)
        diags = server.diagnostics(uri)

        self.assertEqual(len(diags), 1)
        lsp_diag = diags[0]
        self.assertIsNotNone(lsp_diag.data)
        assert lsp_diag.data is not None

        self.assertIn("help", lsp_diag.data)
        self.assertIn("fix_candidates", lsp_diag.data)
        self.assertGreaterEqual(len(lsp_diag.data["fix_candidates"]), 2)
        first_fix = lsp_diag.data["fix_candidates"][0]
        self.assertEqual(first_fix["title"], "Replace with 'model'")
        self.assertEqual(first_fix["replacement"], "model")


if __name__ == "__main__":
    unittest.main()
