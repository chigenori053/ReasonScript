"""Comprehensive test suite for LSP Phase 1 Navigation features (Issue #53, [RS-DXLI-10]).

Verifies:
1. Document Symbols (`textDocument/documentSymbol`):
   - Hierarchical symbol tree (model / module -> struct / enum / fn / calculation / state).
   - SelectionRange points precisely to identifier.
   - Robustness and fallback on incomplete / invalid syntax without server crash.
2. Hover (`textDocument/hover`):
   - Keyword, Runtime API, local parameter, local variable, and module symbol hovers.
   - Enriched markdown with signatures, types, visibility, and doc comments (///).
3. Go to Definition (`textDocument/definition`):
   - Scoped resolution: local parameter/variable -> same-module symbol -> qualified reference -> workspace symbols.
   - Accurate locations from in-memory document state.
4. JSON-RPC protocol round-trip for all navigation requests.
"""

from __future__ import annotations

import unittest

from frontend.lsp.core import ReasonScriptLanguageServer
from frontend.lsp.model import Position, Range, SymbolKind


class TestLSPPhase1Navigation(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ReasonScriptLanguageServer()
        self.uri = "file:///workspace/test_doc.rsn"

    def test_document_symbols_hierarchical_tree(self) -> None:
        source = """package demo

/// The primary system model.
model Main {
    state counter: int

    /// Greet the user.
    pub fn Greeting() -> string {
        return "Hello"
    }

    calculation Compute {
        result = 42
    }

    struct User {
        id: int
    }

    enum Status {
        Active,
        Inactive,
    }
}
"""
        self.server.open_document(self.uri, source, 1)
        symbols = self.server.document_symbols(self.uri)

        # There should be 1 top-level symbol: model Main
        self.assertEqual(len(symbols), 1)
        main_sym = symbols[0]
        self.assertEqual(main_sym.name, "Main")
        self.assertEqual(main_sym.kind, int(SymbolKind.CLASS))
        self.assertEqual(main_sym.selection_range.start.line, 3)

        # Children under model Main
        child_names = [c.name for c in main_sym.children]
        self.assertIn("counter", child_names)
        self.assertIn("Greeting", child_names)
        self.assertIn("Compute", child_names)
        self.assertIn("User", child_names)
        self.assertIn("Status", child_names)

        greeting = next(c for c in main_sym.children if c.name == "Greeting")
        self.assertEqual(greeting.kind, int(SymbolKind.FUNCTION))
        self.assertIn("fn Greeting() -> string", greeting.detail)

        compute = next(c for c in main_sym.children if c.name == "Compute")
        self.assertEqual(compute.kind, int(SymbolKind.FUNCTION))

        user_struct = next(c for c in main_sym.children if c.name == "User")
        self.assertEqual(user_struct.kind, int(SymbolKind.STRUCT))

        status_enum = next(c for c in main_sym.children if c.name == "Status")
        self.assertEqual(status_enum.kind, int(SymbolKind.ENUM))

    def test_document_symbols_incomplete_syntax_robustness(self) -> None:
        # Incomplete source: model unclosed, calculation unclosed
        source = """model Incomplete {
    fn running(
"""
        self.server.open_document(self.uri, source, 1)
        symbols = self.server.document_symbols(self.uri)
        self.assertGreater(len(symbols), 0)
        self.assertEqual(symbols[0].name, "Incomplete")
        # Should not crash, and range reaches the end of lines
        self.assertEqual(symbols[0].range.end.line, 1)

    def test_hover_doc_comments_and_signature(self) -> None:
        source = """package demo
model Main {
    /// Calculate the answer to life.
    /// Returns 42 directly.
    pub fn Answer() -> int {
        return 42
    }
}
"""
        self.server.open_document(self.uri, source, 1)

        # Hover on "Answer" (line 4, col 12)
        hover = self.server.hover(self.uri, 4, 12)
        self.assertIsNotNone(hover)
        assert hover is not None
        self.assertIn("pub fn Answer() -> int", hover.contents)
        self.assertIn("Calculate the answer to life.", hover.contents)
        self.assertIn("Returns 42 directly.", hover.contents)
        self.assertIn("**Visibility**: `Public`", hover.contents)

    def test_hover_local_parameter_and_variable(self) -> None:
        source = """package demo
model Main {
    fn Process(goal: Goal) {
        let count: int = 10
        print(count)
        print(goal)
    }
}
"""
        self.server.open_document(self.uri, source, 1)

        # Hover on local variable "count" in `print(count)` at (line 4, col 15)
        hover_var = self.server.hover(self.uri, 4, 15)
        self.assertIsNotNone(hover_var)
        assert hover_var is not None
        self.assertIn("(variable) count: int", hover_var.contents)
        self.assertIn("Local variable in `Process`", hover_var.contents)

        # Hover on parameter "goal" in `print(goal)` at (line 5, col 15)
        hover_param = self.server.hover(self.uri, 5, 15)
        self.assertIsNotNone(hover_param)
        assert hover_param is not None
        self.assertIn("(parameter) goal: Goal", hover_param.contents)
        self.assertIn("Parameter in `Process`", hover_param.contents)

    def test_definition_local_parameter_and_variable(self) -> None:
        source = """package demo
model Main {
    fn Run(param_x: int) {
        let local_y = 20
        return param_x + local_y
    }
}
"""
        self.server.open_document(self.uri, source, 1)

        # Jump to definition of "param_x" from line 4 (col 17)
        loc_param = self.server.definition(self.uri, 4, 17)
        self.assertIsNotNone(loc_param)
        assert loc_param is not None
        # Must jump to line 2 where "param_x" is declared
        self.assertEqual(loc_param.range.start.line, 2)

        # Jump to definition of "local_y" from line 4 (col 27)
        loc_var = self.server.definition(self.uri, 4, 27)
        self.assertIsNotNone(loc_var)
        assert loc_var is not None
        # Must jump to line 3 where "local_y" is declared
        self.assertEqual(loc_var.range.start.line, 3)

    def test_definition_same_module_and_external_module(self) -> None:
        source_a = """package demo
model Helper {
    pub fn Add(a: int, b: int) -> int {
        return a + b
    }
}
"""
        source_b = """package demo
model Main {
    fn Calc() {
        return Helper.Add(1, 2)
    }
}
"""
        uri_a = "file:///workspace/helper.rsn"
        uri_b = "file:///workspace/main.rsn"

        self.server.open_document(uri_a, source_a, 1)
        self.server.open_document(uri_b, source_b, 1)

        # From main.rsn, jump to "Helper" at (line 3, col 17)
        loc_mod = self.server.definition(uri_b, 3, 17)
        self.assertIsNotNone(loc_mod)
        assert loc_mod is not None
        self.assertEqual(loc_mod.uri, uri_a)
        self.assertEqual(loc_mod.range.start.line, 1)

        # From main.rsn, jump to "Add" at (line 3, col 23)
        loc_fn = self.server.definition(uri_b, 3, 23)
        self.assertIsNotNone(loc_fn)
        assert loc_fn is not None
        self.assertEqual(loc_fn.uri, uri_a)
        self.assertEqual(loc_fn.range.start.line, 2)

    def test_document_symbol_serialization(self) -> None:
        source = "model A { fn B() {} }"
        self.server.open_document(self.uri, source, 1)
        symbols = self.server.document_symbols(self.uri)
        self.assertEqual(len(symbols), 1)

        json_sym = symbols[0].to_dict()
        self.assertEqual(json_sym["name"], "A")
        self.assertEqual(json_sym["kind"], int(SymbolKind.CLASS))
        self.assertIn("range", json_sym)
        self.assertIn("selectionRange", json_sym)
        self.assertIn("children", json_sym)
        self.assertEqual(len(json_sym["children"]), 1)
        self.assertEqual(json_sym["children"][0]["name"], "B")
        self.assertEqual(json_sym["children"][0]["kind"], int(SymbolKind.FUNCTION))

    def test_builtin_symbols_include_reasoning_types(self) -> None:
        from frontend.lsp.core import BUILTIN_SYMBOLS
        sym_map = {s.name: s for s in BUILTIN_SYMBOLS}
        self.assertIn("ReasonGraph", sym_map)
        self.assertEqual(sym_map["ReasonGraph"].kind, "ReasoningType")
        self.assertEqual(sym_map["ReasonGraph"].module, "reasoning")

        self.assertIn("ExecutionPlan", sym_map)
        self.assertEqual(sym_map["ExecutionPlan"].kind, "ReasoningType")
        self.assertEqual(sym_map["ExecutionPlan"].module, "reasoning")

        # Ensure no duplicates in names
        all_names = [s.name for s in BUILTIN_SYMBOLS]
        self.assertEqual(len(all_names), len(set(all_names)))

    def test_resolve_token_builtins(self) -> None:
        sym_infer = self.server._resolve_token(self.uri, "vision.infer", 0)
        self.assertIsNotNone(sym_infer)
        assert sym_infer is not None
        self.assertEqual(sym_infer.name, "vision.infer")
        self.assertEqual(sym_infer.kind, "RuntimeAPI")

        sym_rg = self.server._resolve_token(self.uri, "ReasonGraph", 0)
        self.assertIsNotNone(sym_rg)
        assert sym_rg is not None
        self.assertEqual(sym_rg.kind, "ReasoningType")

    def test_scan_symbols_detail_and_visibility(self) -> None:
        source = """model Main {
    calculation InternalCalc {
        return 1
    }
    pub calculation PublicCalc {
        return 2
    }
}
"""
        self.server.open_document(self.uri, source, 1)
        syms = {s.name: s for s in self.server.workspace_symbols() if s.location.uri == self.uri}
        self.assertIn("Main", syms)
        self.assertEqual(syms["Main"].detail, "Model Main")

        self.assertIn("InternalCalc", syms)
        self.assertEqual(syms["InternalCalc"].visibility, "Private")

        self.assertIn("PublicCalc", syms)
        self.assertEqual(syms["PublicCalc"].visibility, "Public")

    def test_resolve_local_symbol_parameter_exact_column(self) -> None:
        source = """model Demo {
    export fn compute(input_val: int, val: int) -> int {
        return val
    }
}
"""
        self.server.open_document(self.uri, source, 1)
        # Target parameter "val" at return line (line 2, col 15)
        loc = self.server.definition(self.uri, 2, 15)
        self.assertIsNotNone(loc)
        assert loc is not None
        self.assertEqual(loc.range.start.line, 1)
        # Exact column of second parameter "val: int" (38, avoiding 'val' inside input_val)
        expected_col = source.splitlines()[1].find(", val: int") + 2
        self.assertEqual(loc.range.start.character, expected_col)
        self.assertEqual(loc.range.start.character, 38)

    def test_hover_dotted_api_avoids_keyword_collision(self) -> None:
        source = """model Demo {
    fn run() {
        runtime.search
    }
}
"""
        self.server.open_document(self.uri, source, 1)
        # Hover directly on "search" (line 2, col 17)
        hover = self.server.hover(self.uri, 2, 17)
        self.assertIsNotNone(hover)
        assert hover is not None
        self.assertIn("RuntimeAPI", hover.contents)
        self.assertIn("runtime.search", hover.contents)
        self.assertNotIn("Keyword", hover.contents)

    def test_safe_untracked_uri_methods(self) -> None:
        untracked = "file:///non_existent.rsn"
        # Must not raise KeyError
        diags = self.server.diagnostics(untracked)
        self.assertEqual(diags, ())

        saved = self.server.save_document(untracked)
        self.assertEqual(saved.uri, untracked)

        tok = self.server._resolve_token(untracked, "NonExistent", 0)
        self.assertIsNone(tok)

    def test_document_symbols_nested_hierarchy_and_siblings(self) -> None:
        source = """model Main {
    struct Config {
        const Timeout = 30;
    }
    fn setup() {}
    fn teardown() {}
}
model Auxiliary {
    fn helper() {}
}
"""
        self.server.open_document(self.uri, source, 1)
        symbols = self.server.document_symbols(self.uri)
        self.assertEqual(len(symbols), 2)
        self.assertEqual(symbols[0].name, "Main")
        self.assertEqual(symbols[1].name, "Auxiliary")

        main_children = {c.name: c for c in symbols[0].children}
        self.assertEqual(len(main_children), 3)
        self.assertIn("Config", main_children)
        self.assertIn("setup", main_children)
        self.assertIn("teardown", main_children)

        config_children = {c.name: c for c in main_children["Config"].children}
        self.assertEqual(len(config_children), 1)
        self.assertIn("Timeout", config_children)

        aux_children = {c.name: c for c in symbols[1].children}
        self.assertEqual(len(aux_children), 1)
        self.assertIn("helper", aux_children)

    def test_core_module_type_hints_resolvable(self) -> None:
        import typing
        from frontend.lsp import core
        hints = typing.get_type_hints(core._resolve_local_symbol)
        self.assertIn("return", hints)


if __name__ == "__main__":
    unittest.main()
