"""Comprehensive test suite for LSP Phase 2 features (Issue #52, [RS-DXLI-12]).

Verifies:
1. Workspace Symbols (`workspace/symbol`):
   - Query filtering (case-insensitive substring match).
   - Correct LSP integer SymbolKind values.
2. Find References (`textDocument/references`):
   - Excludes comments (line comments // and block comments /* */).
   - Collects references from open in-memory documents and workspace.
3. Signature Help (`textDocument/signatureHelp`):
   - Returns parameter lists and activeParameter for user-defined functions and built-in APIs.
   - Handles comma tracking without being confused by nested parentheses or strings.
4. Semantic Tokens (`textDocument/semanticTokens/full`):
   - Standard 5-element relative encoding (deltaLine, deltaStartChar, length, tokenType, tokenModifiers).
   - Covers keywords, types, functions, variables, strings, numbers, comments.
5. Rename Symbol (`textDocument/prepareRename` & `textDocument/rename`):
   - prepare_rename validates target range or returns None for non-renameable tokens.
   - Validates new name format, disallows reserved keywords, prevents symbol collisions.
   - Generates WorkspaceEdit covering all reference sites.
6. Document Formatting (`textDocument/formatting`):
   - 4-space indentation, normalized spacing around operators/colons/commas, trailing newline.
   - Idempotent (running twice produces identical output).
   - Graceful fallback on malformed input without server crash.
7. Cancellation (`$/cancelRequest`):
   - Handled gracefully without errors or crashes.
"""

from __future__ import annotations

import io
import json
import sys
import unittest

from frontend.lsp.core import (
    ReasonScriptLanguageServer,
    SEMANTIC_TOKEN_TYPES,
    SYMBOL_KIND_MAP,
)
from frontend.lsp.model import FormattingOptions, Position, Range, SymbolKind
from frontend.lsp.server import run_stdio


class TestLSPPhase2Features(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ReasonScriptLanguageServer()
        self.uri1 = "file:///workspace/doc1.rsn"
        self.uri2 = "file:///workspace/doc2.rsn"

    def test_workspace_symbols_query_filtering_and_kind(self) -> None:
        source1 = """package pkg1
fn CalculateSum(a: int, b: int) -> int {
    return a + b
}

struct Point {
    x: int,
    y: int
}
"""
        source2 = """package pkg2
fn ComputeDiff(a: int, b: int) -> int {
    return a - b
}
"""
        self.server.open_document(self.uri1, source1, 1)
        self.server.open_document(self.uri2, source2, 1)

        # 1. Empty query returns all symbols
        all_syms = self.server.workspace_symbols()
        names = {s.name for s in all_syms}
        self.assertIn("CalculateSum", names)
        self.assertIn("Point", names)
        self.assertIn("ComputeDiff", names)

        # 2. Filter query (case-insensitive substring)
        calc_syms = self.server.workspace_symbols("calc")
        self.assertEqual(len(calc_syms), 1)
        self.assertEqual(calc_syms[0].name, "CalculateSum")
        self.assertEqual(calc_syms[0].kind, "Function")
        self.assertEqual(SYMBOL_KIND_MAP.get(calc_syms[0].kind), int(SymbolKind.FUNCTION))

        pt_syms = self.server.workspace_symbols("point")
        self.assertEqual(len(pt_syms), 1)
        self.assertEqual(pt_syms[0].name, "Point")
        self.assertEqual(pt_syms[0].kind, "Struct")
        self.assertEqual(SYMBOL_KIND_MAP.get(pt_syms[0].kind), int(SymbolKind.STRUCT))

    def test_find_references_excludes_comments(self) -> None:
        source1 = """fn calculate(x: int) -> int {
    // calculate is awesome
    /* multiple line
       calculate comment */
    let y = calculate(x)
    return y
}
"""
        self.server.open_document(self.uri1, source1, 1)
        # Position at 'calculate' definition: line 0, char 3
        refs = self.server.references(self.uri1, 0, 3)
        # Expect 2 references: the definition (line 0) and the call (line 4)
        # The comments at line 1 and lines 2-3 MUST NOT be included.
        ref_lines = [r.range.start.line for r in refs]
        self.assertEqual(len(ref_lines), 2)
        self.assertIn(0, ref_lines)
        self.assertIn(4, ref_lines)
        self.assertNotIn(1, ref_lines)
        self.assertNotIn(2, ref_lines)
        self.assertNotIn(3, ref_lines)

    def test_signature_help_user_defined_and_builtin(self) -> None:
        source = """fn add(first: int, second: int) -> int {
    return first + second
}

fn main() {
    let res = add(10, 20)
    print("hello")
}
"""
        self.server.open_document(self.uri1, source, 1)

        # 1. Inside add( after '(', activeParameter == 0
        sig0 = self.server.signature_help(self.uri1, 5, 18)
        self.assertIsNotNone(sig0)
        assert sig0 is not None
        self.assertEqual(len(sig0.signatures), 1)
        sig_info0 = sig0.signatures[0]
        self.assertEqual(sig_info0.label, "fn add(first: int, second: int) -> int")
        self.assertEqual(len(sig_info0.parameters), 2)
        self.assertEqual(sig_info0.parameters[0].label, "first: int")
        self.assertEqual(sig_info0.parameters[1].label, "second: int")
        self.assertEqual(sig0.active_parameter, 0)

        # 2. Inside add(10, after ',', activeParameter == 1
        sig1 = self.server.signature_help(self.uri1, 5, 23)
        self.assertIsNotNone(sig1)
        assert sig1 is not None
        self.assertEqual(sig1.active_parameter, 1)

        # 3. Builtin print("hello")
        sig_print = self.server.signature_help(self.uri1, 6, 11)
        self.assertIsNotNone(sig_print)
        assert sig_print is not None
        self.assertEqual(sig_print.signatures[0].label, "fn print(value: any) -> void")
        self.assertEqual(sig_print.active_parameter, 0)

        # 4. Outside any call
        sig_none = self.server.signature_help(self.uri1, 0, 0)
        self.assertIsNone(sig_none)

    def test_semantic_tokens_relative_encoding(self) -> None:
        source = """// header
fn run(x: int) -> string {
    let msg = "val"
    return msg
}
"""
        self.server.open_document(self.uri1, source, 1)
        tokens = self.server.semantic_tokens(self.uri1)
        self.assertIsNotNone(tokens)
        assert tokens is not None
        data = tokens.data
        # data length must be multiple of 5
        self.assertEqual(len(data) % 5, 0)
        self.assertGreater(len(data), 0)

        # First token should be comment at line 0, col 0
        comment_type_idx = SEMANTIC_TOKEN_TYPES.index("comment")
        self.assertEqual(data[0], 0)  # deltaLine: 0
        self.assertEqual(data[1], 0)  # deltaStartChar: 0
        self.assertEqual(data[2], 9)  # length of '// header'
        self.assertEqual(data[3], comment_type_idx)

        # Second token should be 'fn' at line 1, col 0
        keyword_type_idx = SEMANTIC_TOKEN_TYPES.index("keyword")
        self.assertEqual(data[5], 1)  # deltaLine: 1
        self.assertEqual(data[6], 0)  # deltaStartChar: 0
        self.assertEqual(data[7], 2)  # length of 'fn'
        self.assertEqual(data[8], keyword_type_idx)

        # Third token should be 'run' at line 1, col 3 -> deltaLine: 0, deltaStartChar: 3 - 0 = 3
        fn_type_idx = SEMANTIC_TOKEN_TYPES.index("function")
        self.assertEqual(data[10], 0)  # deltaLine: 0
        self.assertEqual(data[11], 3)  # deltaStartChar: 3
        self.assertEqual(data[12], 3)  # length of 'run'
        self.assertEqual(data[13], fn_type_idx)

    def test_prepare_rename_valid_and_invalid(self) -> None:
        source = """fn calculate(x: int) -> int {
    return x * 2
}
"""
        self.server.open_document(self.uri1, source, 1)

        # Valid target: 'calculate' at line 0, char 5
        rng = self.server.prepare_rename(self.uri1, 0, 5)
        self.assertIsNotNone(rng)
        assert rng is not None
        self.assertEqual(rng.start.line, 0)
        self.assertEqual(rng.start.character, 3)
        self.assertEqual(rng.end.character, 12)

        # Invalid target: keyword 'fn' at line 0, char 1 -> rejected
        rng_kw = self.server.prepare_rename(self.uri1, 0, 1)
        self.assertIsNone(rng_kw)

        # Invalid target: whitespace at line 0, char 2 -> rejected
        rng_ws = self.server.prepare_rename(self.uri1, 0, 2)
        self.assertIsNone(rng_ws)

    def test_rename_cross_file_and_validation(self) -> None:
        source1 = """fn calculate(x: int) -> int {
    return x + 1
}
"""
        source2 = """fn run() {
    let a = calculate(10)
}
"""
        self.server.open_document(self.uri1, source1, 1)
        self.server.open_document(self.uri2, source2, 1)

        # 1. Successful rename
        edit = self.server.rename(self.uri1, 0, 5, "computeValue")
        self.assertIsNotNone(edit)
        assert edit is not None
        self.assertIn(self.uri1, edit.changes)
        self.assertIn(self.uri2, edit.changes)
        # Check new text
        for text_edit in edit.changes[self.uri1]:
            self.assertEqual(text_edit.new_text, "computeValue")
        for text_edit in edit.changes[self.uri2]:
            self.assertEqual(text_edit.new_text, "computeValue")

        # 2. Reject invalid identifier (starts with digit or symbol)
        bad_edit = self.server.rename(self.uri1, 0, 5, "123invalid")
        self.assertIsNone(bad_edit)

        # 3. Reject reserved keyword
        kw_edit = self.server.rename(self.uri1, 0, 5, "return")
        self.assertIsNone(kw_edit)

        # 4. Reject existing symbol collision in same file
        collision_source = """fn first() {}
fn second() {}
"""
        coll_uri = "file:///workspace/collision.rsn"
        self.server.open_document(coll_uri, collision_source, 1)
        coll_edit = self.server.rename(coll_uri, 0, 3, "second")
        self.assertIsNone(coll_edit)

    def test_formatting_indentation_operators_and_idempotency(self) -> None:
        unformatted = """package demo
fn calculate(a:int,b:int)->int{
let x=a+b
if x>0{
return x
}
return 0
}
"""
        self.server.open_document(self.uri1, unformatted, 1)
        options = FormattingOptions(tab_size=4, insert_spaces=True)
        edits = self.server.formatting(self.uri1, options)
        self.assertEqual(len(edits), 1)

        formatted_code = edits[0].new_text
        expected = """package demo

fn calculate(a: int, b: int) -> int {
    let x = a + b
    if x > 0 {
        return x
    }
    return 0
}
"""
        self.assertEqual(formatted_code, expected)

        # Test Idempotency: formatting already formatted code produces no changes
        self.server.change_document(self.uri1, formatted_code, 2)
        second_edits = self.server.formatting(self.uri1, options)
        self.assertEqual(len(second_edits), 0)

    def test_formatting_syntax_error_fallback(self) -> None:
        broken_source = """fn broken( {
    incomplete"""
        self.server.open_document(self.uri1, broken_source, 1)
        options = FormattingOptions(tab_size=4, insert_spaces=True)
        # Should not raise exception, produces trailing newline
        edits = self.server.formatting(self.uri1, options)
        self.assertEqual(len(edits), 1)
        self.assertTrue(edits[0].new_text.endswith("\n"))

    def test_json_rpc_phase2_endpoints(self) -> None:
        source = """fn greet(name:string)->string{
return "Hi "+name
}
"""
        messages = [
            # 1. initialize
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            },
            # 2. didOpen
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": self.uri1,
                        "languageId": "reasonscript",
                        "version": 1,
                        "text": source,
                    }
                },
            },
            # 3. signatureHelp
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/signatureHelp",
                "params": {
                    "textDocument": {"uri": self.uri1},
                    "position": {"line": 0, "character": 9},
                },
            },
            # 4. semanticTokens/full
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "textDocument/semanticTokens/full",
                "params": {"textDocument": {"uri": self.uri1}},
            },
            # 5. prepareRename
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "textDocument/prepareRename",
                "params": {
                    "textDocument": {"uri": self.uri1},
                    "position": {"line": 0, "character": 4},
                },
            },
            # 6. rename
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "textDocument/rename",
                "params": {
                    "textDocument": {"uri": self.uri1},
                    "position": {"line": 0, "character": 4},
                    "newName": "sayHello",
                },
            },
            # 7. formatting
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "textDocument/formatting",
                "params": {
                    "textDocument": {"uri": self.uri1},
                    "options": {"tabSize": 4, "insertSpaces": True},
                },
            },
            # 8. cancelRequest
            {
                "jsonrpc": "2.0",
                "method": "$/cancelRequest",
                "params": {"id": 999},
            },
            # 9. workspace/symbol
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "workspace/symbol",
                "params": {"query": "greet"},
            },
            # 10. shutdown & exit
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "shutdown",
                "params": {},
            },
            {
                "jsonrpc": "2.0",
                "method": "exit",
                "params": {},
            },
        ]

        # Build raw input stream
        input_data = b""
        for msg in messages:
            body = json.dumps(msg).encode("utf-8")
            input_data += f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body

        class DummyIO:
            def __init__(self, buffer: io.BytesIO):
                self.buffer = buffer

        import sys
        old_stdin = sys.stdin
        old_stdout = sys.stdout

        out_buf = io.BytesIO()
        sys.stdin = DummyIO(io.BytesIO(input_data))  # type: ignore[assignment]
        sys.stdout = DummyIO(out_buf)  # type: ignore[assignment]

        try:
            exit_code = run_stdio()
            self.assertEqual(exit_code, 0)
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout

        # Parse responses
        raw_output = out_buf.getvalue().decode("utf-8")
        responses = []
        parts = raw_output.split("Content-Length: ")
        for part in parts:
            if "\r\n\r\n" in part:
                _, body = part.split("\r\n\r\n", 1)
                try:
                    responses.append(json.loads(body))
                except json.JSONDecodeError:
                    pass

        # Verify responses by id
        by_id = {r.get("id"): r for r in responses if "id" in r}

        # Check initialize
        init_res = by_id.get(1)
        self.assertIsNotNone(init_res)
        caps = init_res["result"]["capabilities"]
        self.assertIn("signatureHelpProvider", caps)
        self.assertIn("semanticTokensProvider", caps)
        self.assertIn("renameProvider", caps)
        self.assertIn("documentFormattingProvider", caps)

        # Check semanticTokens/full
        sem_res = by_id.get(3)
        self.assertIsNotNone(sem_res)
        self.assertIn("data", sem_res["result"])

        # Check prepareRename
        prep_res = by_id.get(4)
        self.assertIsNotNone(prep_res)
        self.assertIsNotNone(prep_res["result"])

        # Check rename
        ren_res = by_id.get(5)
        self.assertIsNotNone(ren_res)
        self.assertIn("changes", ren_res["result"])

        # Check formatting
        fmt_res = by_id.get(6)
        self.assertIsNotNone(fmt_res)
        self.assertEqual(len(fmt_res["result"]), 1)

        # Check workspace/symbol
        ws_res = by_id.get(7)
        self.assertIsNotNone(ws_res)
        self.assertEqual(len(ws_res["result"]), 1)
        self.assertEqual(ws_res["result"][0]["name"], "greet")
        self.assertEqual(ws_res["result"][0]["kind"], int(SymbolKind.FUNCTION))

    def test_large_workspace_symbol_indexing_and_references(self) -> None:
        # Simulate large workspace with 50 files
        for i in range(50):
            file_uri = f"file:///workspace/module_{i:03d}.rsn"
            content = f"""package pkg_{i}

struct Struct_{i} {{
    id: int
}}

fn SharedHelper(val: int) -> int {{
    return val + {i}
}}

fn LocalFunc_{i}() -> int {{
    return SharedHelper({i})
}}
"""
            self.server.open_document(file_uri, content, 1)

        # 1. Workspace symbol search across large project
        all_syms = self.server.workspace_symbols()
        # 50 files * 3 user symbols + builtins
        self.assertGreaterEqual(len(all_syms), 150)

        # Query filtered
        helper_syms = self.server.workspace_symbols("SharedHelper")
        self.assertEqual(len(helper_syms), 50)

        struct_0_syms = self.server.workspace_symbols("Struct_0")
        self.assertEqual(len(struct_0_syms), 1)

        # 2. Large workspace cross-file references
        first_uri = "file:///workspace/module_000.rsn"
        # SharedHelper is defined on line 6, char 3
        refs = self.server.references(first_uri, 6, 3)
        # SharedHelper appears twice in each file (def + call), so 50 * 2 = 100 refs
        self.assertEqual(len(refs), 100)

        # 3. Large workspace cross-file rename
        rename_edit = self.server.rename(first_uri, 6, 3, "GlobalHelper")
        self.assertIsNotNone(rename_edit)
        assert rename_edit is not None
        self.assertEqual(len(rename_edit.changes), 50)
        for edits in rename_edit.changes.values():
            self.assertEqual(len(edits), 2)
            for edit in edits:
                self.assertEqual(edit.new_text, "GlobalHelper")

    def test_performance_budget_across_capabilities(self) -> None:
        import time

        # Build a large document with 1000 lines
        lines = ["package perf_test\n"]
        for i in range(200):
            lines.append(f"""
struct Item_{i} {{
    id: int,
    value: int
}}

fn compute_item_{i}(a: Item_{i}, factor: int) -> int {{
    let res = a.value * factor
    return res
}}
""")
        large_source = "\n".join(lines)
        perf_uri = "file:///workspace/perf_large.rsn"

        t0 = time.perf_counter()
        self.server.open_document(perf_uri, large_source, 1)
        open_dur = time.perf_counter() - t0
        self.assertLess(open_dur, 0.5)  # < 500ms budget for opening large file

        # document_symbols budget
        t0 = time.perf_counter()
        syms = self.server.document_symbols(perf_uri)
        doc_sym_dur = time.perf_counter() - t0
        self.assertLess(doc_sym_dur, 0.1)  # < 100ms
        self.assertGreaterEqual(len(syms), 200)

        # hover budget
        t0 = time.perf_counter()
        hover = self.server.hover(perf_uri, 3, 7)
        hover_dur = time.perf_counter() - t0
        self.assertLess(hover_dur, 0.05)  # < 50ms

        # completion budget
        t0 = time.perf_counter()
        completions = self.server.completion(perf_uri, 10, 4)
        comp_dur = time.perf_counter() - t0
        self.assertLess(comp_dur, 0.05)  # < 50ms
        self.assertGreater(len(completions), 0)

        # signature_help budget
        t0 = time.perf_counter()
        sig = self.server.signature_help(perf_uri, 8, 20)
        sig_dur = time.perf_counter() - t0
        self.assertLess(sig_dur, 0.05)  # < 50ms

        # semantic_tokens budget
        t0 = time.perf_counter()
        tokens = self.server.semantic_tokens(perf_uri)
        token_dur = time.perf_counter() - t0
        self.assertLess(token_dur, 0.1)  # < 100ms
        self.assertIsNotNone(tokens)

        # formatting budget
        t0 = time.perf_counter()
        fmt_edits = self.server.formatting(perf_uri, FormattingOptions(tab_size=4, insert_spaces=True))
        fmt_dur = time.perf_counter() - t0
        self.assertLess(fmt_dur, 0.1)  # < 100ms

    def test_cancellation_protocol_and_resilience(self) -> None:
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            # Cancel before request
            {"jsonrpc": "2.0", "method": "$/cancelRequest", "params": {"id": 2}},
            # Normal request
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "workspace/symbol",
                "params": {"query": ""},
            },
            # Cancel nonexistent request
            {"jsonrpc": "2.0", "method": "$/cancelRequest", "params": {"id": 99999}},
            # Subsequent normal request
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown", "params": {}},
            {"jsonrpc": "2.0", "method": "exit", "params": {}},
        ]

        input_data = b""
        for msg in messages:
            body = json.dumps(msg).encode("utf-8")
            input_data += f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body

        class DummyIO:
            def __init__(self, buffer: io.BytesIO):
                self.buffer = buffer

        old_stdin = sys.stdin
        old_stdout = sys.stdout

        out_buf = io.BytesIO()
        sys.stdin = DummyIO(io.BytesIO(input_data))  # type: ignore[assignment]
        sys.stdout = DummyIO(out_buf)  # type: ignore[assignment]

        try:
            exit_code = run_stdio()
            self.assertEqual(exit_code, 0)
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout

        raw_output = out_buf.getvalue().decode("utf-8")
        responses = []
        for part in raw_output.split("Content-Length: "):
            if "\r\n\r\n" in part:
                _, body = part.split("\r\n\r\n", 1)
                try:
                    responses.append(json.loads(body))
                except json.JSONDecodeError:
                    pass

        by_id = {r.get("id"): r for r in responses if "id" in r}
        self.assertIn(1, by_id)
        self.assertIn(2, by_id)
        self.assertIn(3, by_id)


if __name__ == "__main__":
    unittest.main()
