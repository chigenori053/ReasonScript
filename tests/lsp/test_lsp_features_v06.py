"""Tests for refreshed LSP features in v0.6-D: diagnostics push, code actions, rich completions, and hover."""

from __future__ import annotations

import unittest

from frontend.lsp.core import ReasonScriptLanguageServer
from frontend.lsp.model import Position, Range
from frontend.lsp.server import _diagnostic_json


class TestLSPRefreshedFeatures(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ReasonScriptLanguageServer()
        self.uri = "file:///workspace/test_doc.rsn"

    def test_publish_diagnostics_data_payload(self) -> None:
        source = "world BrokenWorld {}"
        state = self.server.open_document(self.uri, source, 1)
        self.assertGreater(len(state.diagnostics), 0)

        diag = state.diagnostics[0]
        json_diag = _diagnostic_json(diag)

        self.assertEqual(json_diag["code"], "PAR-0002")
        self.assertIn("data", json_diag)
        data = json_diag["data"]
        self.assertIn("fix_candidates", data)
        self.assertGreater(len(data["fix_candidates"]), 0)
        self.assertEqual(data["fix_candidates"][0]["title"], "Replace with 'model'")

    def test_code_actions_generate_quickfix_workspace_edits(self) -> None:
        source = "world BrokenWorld {}"
        self.server.open_document(self.uri, source, 1)

        req_range = Range(Position(0, 0), Position(0, 5))
        actions = self.server.code_actions(self.uri, req_range)

        self.assertGreaterEqual(len(actions), 2)
        model_fix = actions[0]
        self.assertEqual(model_fix.title, "Replace with 'model'")
        self.assertEqual(model_fix.kind, "quickfix")
        self.assertTrue(model_fix.is_preferred)
        self.assertIsNotNone(model_fix.edit)
        self.assertIn(self.uri, model_fix.edit.changes)

        edits = model_fix.edit.changes[self.uri]
        self.assertEqual(len(edits), 1)
        self.assertEqual(edits[0].new_text, "model")

        action_dict = model_fix.to_dict()
        self.assertEqual(action_dict["title"], "Replace with 'model'")
        self.assertEqual(action_dict["kind"], "quickfix")
        self.assertTrue(action_dict["isPreferred"])
        self.assertIn("edit", action_dict)

    def test_completion_dot_runtime(self) -> None:
        source = "package demo\nmodel Demo {\n  fn test() {\n    runtime.\n  }\n}\n"
        self.server.open_document(self.uri, source, 1)

        # Cursor at line 3, after "runtime." (col 12)
        items = self.server.completion(self.uri, 3, 12)
        labels = [item.label for item in items]

        self.assertIn("runtime.search", labels)
        self.assertIn("runtime.plan", labels)
        self.assertIn("runtime.predict", labels)
        self.assertIn("runtime.simulate", labels)
        # Should NOT contain random keywords when requesting runtime. dot completion
        self.assertNotIn("model", labels)
        self.assertNotIn("module", labels)

    def test_completion_rich_metadata_and_documentation(self) -> None:
        source = "model Demo {}\n"
        self.server.open_document(self.uri, source, 1)

        items = self.server.completion(self.uri, 0, 0)
        item_map = {item.label: item for item in items}

        self.assertIn("model", item_map)
        model_item = item_map["model"]
        self.assertIn("model <Name>", model_item.detail)
        self.assertIn("preferred top-level construct", model_item.documentation)

        self.assertIn("runtime.search", item_map)
        search_item = item_map["runtime.search"]
        self.assertIn("fn search", search_item.detail)
        self.assertIn("guided state-space search", search_item.documentation)

    def test_hover_markdown_for_api_and_keyword(self) -> None:
        source = "model Demo {\n  fn run() {\n    runtime.search\n  }\n}\n"
        self.server.open_document(self.uri, source, 1)

        # Hover on "model" at (0, 2)
        hover_model = self.server.hover(self.uri, 0, 2)
        self.assertIsNotNone(hover_model)
        self.assertIn("```reasonscript", hover_model.contents)
        self.assertIn("model <Name>", hover_model.contents)
        self.assertIn("Keyword", hover_model.contents)

        # Hover on "runtime.search" at (2, 8)
        hover_api = self.server.hover(self.uri, 2, 8)
        self.assertIsNotNone(hover_api)
        self.assertIn("```reasonscript", hover_api.contents)
        self.assertIn("runtime.search", hover_api.contents)
        self.assertIn("RuntimeAPI", hover_api.contents)

    def test_hover_for_user_defined_constructs(self) -> None:
        source = "model Demo {\n  pub fn calculate(x: int) -> int {\n    return x\n  }\n}\n"
        self.server.open_document(self.uri, source, 1)

        # Hover on "calculate" at line 1, col 11
        hover_fn = self.server.hover(self.uri, 1, 11)
        self.assertIsNotNone(hover_fn)
        self.assertIn("```reasonscript", hover_fn.contents)
        self.assertIn("pub fn calculate(x: int) -> int", hover_fn.contents)
        self.assertIn("Function", hover_fn.contents)
        self.assertIn("Name: calculate", hover_fn.contents)

    def test_definition_jump_for_model_and_function(self) -> None:
        source = "model Demo {\n  fn helper() {}\n  fn main() {\n    helper()\n  }\n}\n"
        self.server.open_document(self.uri, source, 1)

        # Go to definition of "helper" call at line 3, col 6
        loc = self.server.definition(self.uri, 3, 6)
        self.assertIsNotNone(loc)
        self.assertEqual(loc.uri, self.uri)
        self.assertEqual(loc.range.start.line, 1)
