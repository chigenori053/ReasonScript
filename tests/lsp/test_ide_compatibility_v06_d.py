"""IDE Compatibility v0.6-D regression tests.

Specification: reasonscript-ide-compatibility/0.6-D
Target Language: ReasonScript Language Surface v0.5 + v0.6-B/C/D
Phase: IDE-1 — LSP v0.6-D Compatibility
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from frontend.lsp.core import (
    DECLARATION_PATTERNS,
    KEYWORD_COMPLETIONS,
    ReasonScriptLanguageServer,
    _module_for_line,
)


# ---------------------------------------------------------------------------
# Paths to static assets under test
# ---------------------------------------------------------------------------

GRAMMAR_PATH = REPO_ROOT / "vscode-extension" / "syntaxes" / "reasonscript.tmLanguage.json"
APP_TSX_PATH = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src" / "App.tsx"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_grammar_tokens() -> set[str]:
    """Collect every bareword token appearing in any regex inside the grammar."""
    data = json.loads(GRAMMAR_PATH.read_text())
    tokens: set[str] = set()

    def _walk(obj: object) -> None:
        if isinstance(obj, dict):
            if "match" in obj:
                for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", obj["match"]):
                    tokens.add(word)
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(data)
    return tokens


# ---------------------------------------------------------------------------
# §6 — LSP Keyword Completion Policy
# ---------------------------------------------------------------------------

class TestLSPKeywordCompletion:
    """Spec §6: LSP completion policy."""

    REQUIRED = [
        "model", "module", "pub", "fn", "struct", "enum", "calculation",
        "goal", "state", "constraint", "transition", "relation",
        "if", "elif", "else", "match", "when",
        "for", "while", "loop", "break", "continue", "return",
        "input", "print", "search", "simulate", "predict", "plan",
        "true", "false", "some", "none",
    ]
    EXCLUDED = ["world", "system", "component"]

    def test_model_is_first(self) -> None:
        """Spec §6.2: model must be first completion (preferred construct)."""
        assert KEYWORD_COMPLETIONS[0] == "model", (
            f"model must be first in KEYWORD_COMPLETIONS, got '{KEYWORD_COMPLETIONS[0]}'"
        )

    def test_module_is_second(self) -> None:
        """Spec §6.2: module immediately follows model as compatible construct."""
        assert KEYWORD_COMPLETIONS[1] == "module", (
            f"module must be second in KEYWORD_COMPLETIONS, got '{KEYWORD_COMPLETIONS[1]}'"
        )

    def test_all_required_keywords_present(self) -> None:
        """Spec §6.1: all required completion keywords must be in KEYWORD_COMPLETIONS."""
        missing = [kw for kw in self.REQUIRED if kw not in KEYWORD_COMPLETIONS]
        assert not missing, f"Missing from KEYWORD_COMPLETIONS: {missing}"

    def test_reserved_constructs_excluded(self) -> None:
        """Spec §6.3: world / system / component must NOT appear in completions."""
        present = [kw for kw in self.EXCLUDED if kw in KEYWORD_COMPLETIONS]
        assert not present, (
            f"Reserved constructs must not be in KEYWORD_COMPLETIONS: {present}"
        )

    def test_lsp_server_completion_includes_model(self) -> None:
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", "model Demo {}\n", 1)
        labels = {item.label for item in server.completion("file:///t.rsn", 0, 0)}
        assert "model" in labels

    def test_lsp_server_completion_excludes_reserved(self) -> None:
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", "", 1)
        labels = {item.label for item in server.completion("file:///t.rsn", 0, 0)}
        for reserved in self.EXCLUDED:
            assert reserved not in labels, (
                f"Reserved keyword '{reserved}' must not appear in LSP completions"
            )

    def test_lsp_server_completion_includes_control_flow(self) -> None:
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", "", 1)
        labels = {item.label for item in server.completion("file:///t.rsn", 0, 0)}
        for kw in ["if", "elif", "else", "when", "for", "while", "loop", "break", "continue"]:
            assert kw in labels, f"Control-flow keyword '{kw}' missing from LSP completion"

    def test_lsp_server_completion_includes_literals(self) -> None:
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", "", 1)
        labels = {item.label for item in server.completion("file:///t.rsn", 0, 0)}
        for lit in ["true", "false", "some", "none"]:
            assert lit in labels, f"Literal keyword '{lit}' missing from LSP completion"


# ---------------------------------------------------------------------------
# §7 — LSP Declaration Scan Policy
# ---------------------------------------------------------------------------

class TestLSPDeclarationScan:
    """Spec §7: LSP symbol scan policy."""

    def test_declaration_patterns_model_is_first(self) -> None:
        """Spec §7.1: Model must be first pattern (preferred construct)."""
        assert DECLARATION_PATTERNS[0][0] == "Model", (
            f"First DECLARATION_PATTERNS entry must be 'Model', got '{DECLARATION_PATTERNS[0][0]}'"
        )

    def test_declaration_patterns_module_is_second(self) -> None:
        """Spec §7.1: Module must be second pattern (compatible construct)."""
        assert DECLARATION_PATTERNS[1][0] == "Module", (
            f"Second DECLARATION_PATTERNS entry must be 'Module', got '{DECLARATION_PATTERNS[1][0]}'"
        )

    def test_no_world_pattern(self) -> None:
        """Spec §7.3: world must not be in DECLARATION_PATTERNS."""
        kinds = {k for k, _ in DECLARATION_PATTERNS}
        assert "World" not in kinds, "World must not be in DECLARATION_PATTERNS (reserved §7.3)"

    def test_no_scene_pattern(self) -> None:
        """Spec §7.4: legacy WorldModel terms must not be scanned."""
        kinds = {k for k, _ in DECLARATION_PATTERNS}
        assert "Scene" not in kinds

    def test_no_entity_pattern(self) -> None:
        kinds = {k for k, _ in DECLARATION_PATTERNS}
        assert "Entity" not in kinds

    def test_model_pattern_matches_bare(self) -> None:
        _, pat = DECLARATION_PATTERNS[0]
        m = re.search(pat, "model Demo {")
        assert m is not None and m.group(1) == "Demo"

    def test_model_pattern_matches_pub(self) -> None:
        _, pat = DECLARATION_PATTERNS[0]
        m = re.search(pat, "pub model Demo {")
        assert m is not None and m.group(1) == "Demo"

    def test_module_pattern_matches_bare(self) -> None:
        _, pat = DECLARATION_PATTERNS[1]
        m = re.search(pat, "module Legacy {")
        assert m is not None and m.group(1) == "Legacy"

    def test_server_scans_model_symbol(self) -> None:
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", "model Demo {\n}\n", 1)
        user_syms = [s for s in server.workspace_symbols() if s.location.uri != "builtin://reasonscript-lsp"]
        assert any(s.name == "Demo" for s in user_syms), "model declaration not scanned"

    def test_server_model_symbol_kind(self) -> None:
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", "model Demo {\n}\n", 1)
        syms = [s for s in server.workspace_symbols() if s.name == "Demo" and s.location.uri != "builtin://reasonscript-lsp"]
        assert syms and syms[0].kind == "Model", f"Expected kind 'Model', got '{syms[0].kind if syms else 'none'}'"

    def test_server_scans_module_symbol(self) -> None:
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", "module Legacy {\n}\n", 1)
        user_syms = [s for s in server.workspace_symbols() if s.location.uri != "builtin://reasonscript-lsp"]
        assert any(s.name == "Legacy" for s in user_syms), "module declaration not scanned"

    def test_server_module_symbol_kind(self) -> None:
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", "module Legacy {\n}\n", 1)
        syms = [s for s in server.workspace_symbols() if s.name == "Legacy" and s.location.uri != "builtin://reasonscript-lsp"]
        assert syms and syms[0].kind == "Module"

    def test_world_not_scanned(self) -> None:
        """Spec §7.3: world (reserved) must not produce a user symbol."""
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", "world Demo {\n}\n", 1)
        user_syms = [s for s in server.workspace_symbols() if s.location.uri != "builtin://reasonscript-lsp" and s.name == "Demo"]
        assert not user_syms, "world is reserved and must not be registered as symbol"

    def test_system_not_scanned(self) -> None:
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", "system Demo {\n}\n", 1)
        user_syms = [s for s in server.workspace_symbols() if s.location.uri != "builtin://reasonscript-lsp" and s.name == "Demo"]
        assert not user_syms, "system is reserved and must not be registered as symbol"

    def test_component_not_scanned(self) -> None:
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", "component Demo {\n}\n", 1)
        user_syms = [s for s in server.workspace_symbols() if s.location.uri != "builtin://reasonscript-lsp" and s.name == "Demo"]
        assert not user_syms, "component is reserved and must not be registered as symbol"


# ---------------------------------------------------------------------------
# §8 — LSP Scope Detection Policy
# ---------------------------------------------------------------------------

class TestLSPScopeDetection:
    """Spec §8: _module_for_line recognises both model and module."""

    def test_model_scope(self) -> None:
        source = "model Demo {\n  fn run() {}\n}\n"
        assert _module_for_line(source, 1) == "Demo"

    def test_module_scope(self) -> None:
        source = "module Legacy {\n  fn run() {}\n}\n"
        assert _module_for_line(source, 1) == "Legacy"

    def test_pub_model_scope(self) -> None:
        source = "pub model Alpha {\n  fn run() {}\n}\n"
        assert _module_for_line(source, 1) == "Alpha"

    def test_package_with_model(self) -> None:
        source = "package myapp\nmodel Demo {\n  fn run() {}\n}\n"
        assert _module_for_line(source, 2) == "myapp.Demo"

    def test_package_with_module(self) -> None:
        source = "package myapp\nmodule Legacy {\n  fn run() {}\n}\n"
        assert _module_for_line(source, 2) == "myapp.Legacy"

    def test_no_scope_returns_main(self) -> None:
        assert _module_for_line("fn run() {}\n", 0) == "main"

    def test_world_does_not_create_scope(self) -> None:
        """world is reserved; _module_for_line must not treat it as top-level scope."""
        source = "world Demo {\n  fn run() {}\n}\n"
        assert _module_for_line(source, 1) == "main", (
            "world is a reserved construct and must not be treated as a scope boundary"
        )


# ---------------------------------------------------------------------------
# §9 — VS Code Grammar Policy
# ---------------------------------------------------------------------------

class TestVSCodeGrammarSync:
    """Spec §9: tmLanguage.json keyword coverage."""

    REQUIRED_ACTIVE = [
        "model", "module", "pub", "fn", "struct", "enum", "calculation",
        "if", "elif", "else", "match", "when", "for", "while", "loop",
        "return", "break", "continue", "relation",
    ]
    REQUIRED_RESERVED = ["world", "system", "component"]
    REQUIRED_LITERALS = ["true", "false", "some", "none"]

    def _tokens(self) -> set[str]:
        return _all_grammar_tokens()

    def test_active_keywords_in_grammar(self) -> None:
        tokens = self._tokens()
        missing = [kw for kw in self.REQUIRED_ACTIVE if kw not in tokens]
        assert not missing, f"Missing active keywords in tmLanguage.json: {missing}"

    def test_reserved_keywords_in_grammar(self) -> None:
        tokens = self._tokens()
        missing = [kw for kw in self.REQUIRED_RESERVED if kw not in tokens]
        assert not missing, f"Reserved keywords must appear in tmLanguage.json for highlighting: {missing}"

    def test_literals_in_grammar(self) -> None:
        tokens = self._tokens()
        missing = [lit for lit in self.REQUIRED_LITERALS if lit not in tokens]
        assert not missing, f"Missing literal keywords in tmLanguage.json: {missing}"

    def test_reserved_scope_present(self) -> None:
        """Spec §9.2: reserved keywords should use keyword.other.reserved scope."""
        text = GRAMMAR_PATH.read_text()
        assert "reserved" in text, (
            "tmLanguage.json must define a reserved keyword scope (keyword.other.reserved)"
        )


# ---------------------------------------------------------------------------
# §11 — Desktop IDE Default Template
# ---------------------------------------------------------------------------

class TestDesktopIDETemplate:
    """Spec §11: Desktop IDE must use model as default template."""

    def _app_text(self) -> str:
        return APP_TSX_PATH.read_text()

    def test_default_template_uses_model(self) -> None:
        """Spec §11.1: DEFAULT_SOURCE must start with model HelloWorld."""
        assert "model HelloWorld" in self._app_text(), (
            "DEFAULT_SOURCE in App.tsx must use 'model HelloWorld' per spec §11.1"
        )

    def test_default_template_not_module(self) -> None:
        """Spec §11.2: module HelloWorld must not be used as new-code template."""
        assert "module HelloWorld" not in self._app_text(), (
            "DEFAULT_SOURCE must not use 'module HelloWorld' per spec §11.2"
        )

    def test_monaco_language_is_reasonscript(self) -> None:
        """Spec §10.1: Monaco editor must use reasonscript language ID.

        Accepts either the literal string 'reasonscript' or the
        REASONSCRIPT_LANGUAGE_ID constant (whose value is 'reasonscript').
        """
        text = self._app_text()
        assert "REASONSCRIPT_LANGUAGE_ID" in text or "reasonscript" in text, (
            "Monaco editor must register and use reasonscript language per spec §10. "
            "Expected REASONSCRIPT_LANGUAGE_ID constant or literal 'reasonscript' in App.tsx."
        )


# ---------------------------------------------------------------------------
# §13.2 — Positive integration cases
# ---------------------------------------------------------------------------

class TestPositiveCases:
    """Spec §13.2: inputs that must be recognised without errors."""

    def test_model_with_calculation(self) -> None:
        source = "model Demo {\n  calculation Result {\n    result = 42\n  }\n}\n"
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", source, 1)
        names = {s.name for s in server.workspace_symbols() if s.location.uri != "builtin://reasonscript-lsp"}
        assert "Demo" in names

    def test_module_with_calculation(self) -> None:
        source = "module Legacy {\n  calculation Result {\n    result = 42\n  }\n}\n"
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", source, 1)
        names = {s.name for s in server.workspace_symbols() if s.location.uri != "builtin://reasonscript-lsp"}
        assert "Legacy" in names

    def test_model_with_pub_fn(self) -> None:
        source = (
            "model ControlFlow {\n"
            "  pub fn Select(flag: bool) -> int {\n"
            "    if flag {\n"
            "      return 1\n"
            "    } elif false {\n"
            "      return 2\n"
            "    } else {\n"
            "      return 0\n"
            "    }\n"
            "  }\n"
            "}\n"
        )
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", source, 1)
        names = {s.name for s in server.workspace_symbols() if s.location.uri != "builtin://reasonscript-lsp"}
        assert "ControlFlow" in names
        assert "Select" in names

    def test_scope_inside_model(self) -> None:
        source = "model Alpha {\n  fn run() {}\n}\n"
        assert _module_for_line(source, 1) == "Alpha"

    def test_scope_inside_module(self) -> None:
        source = "module Beta {\n  fn run() {}\n}\n"
        assert _module_for_line(source, 1) == "Beta"


# ---------------------------------------------------------------------------
# §13.3 — Negative cases
# ---------------------------------------------------------------------------

class TestNegativeCases:
    """Spec §13.3: reserved constructs must not be accepted as symbols."""

    RESERVED = ["world", "system", "component"]

    def test_reserved_not_in_completion(self) -> None:
        server = ReasonScriptLanguageServer()
        server.open_document("file:///t.rsn", "", 1)
        labels = {item.label for item in server.completion("file:///t.rsn", 0, 0)}
        for r in self.RESERVED:
            assert r not in labels, f"Reserved '{r}' must not appear in completions"

    def test_reserved_not_scanned_as_symbols(self) -> None:
        for construct in self.RESERVED:
            server = ReasonScriptLanguageServer()
            server.open_document("file:///t.rsn", f"{construct} Demo {{\n}}\n", 1)
            user_syms = [
                s for s in server.workspace_symbols()
                if s.location.uri != "builtin://reasonscript-lsp" and s.name == "Demo"
            ]
            assert not user_syms, (
                f"'{construct} Demo' must not be registered as symbol (reserved §7.3)"
            )

    def test_reserved_not_scope_boundary(self) -> None:
        for construct in self.RESERVED:
            source = f"{construct} Demo {{\n  fn run() {{}}\n}}\n"
            scope = _module_for_line(source, 1)
            assert scope == "main", (
                f"'{construct}' must not create a scope boundary; expected 'main', got '{scope}'"
            )
