"""Minimal stdio JSON-RPC transport for ReasonScript LSP Phase 1."""

from __future__ import annotations

import json
import sys
from typing import Any

from .core import ReasonScriptLanguageServer, SEMANTIC_TOKENS_LEGEND, SYMBOL_KIND_MAP
from .model import DiagnosticSeverity, FormattingOptions, Position, Range


def _read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in {b"\r\n", b"\n"}:
            break
        key, value = line.decode("ascii").split(":", 1)
        headers[key.lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))


def _send(payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def _position(params: dict[str, Any]) -> tuple[str, int, int]:
    document = params["textDocument"]["uri"]
    position = params.get("position", {})
    return document, int(position.get("line", 0)), int(position.get("character", 0))


def _publish_diagnostics(uri: str, diagnostics: tuple[Any, ...]) -> None:
    _send({
        "jsonrpc": "2.0",
        "method": "textDocument/publishDiagnostics",
        "params": {
            "uri": uri,
            "diagnostics": [_diagnostic_json(item) for item in diagnostics],
        },
    })


def run_stdio() -> int:
    server = ReasonScriptLanguageServer()
    while True:
        request = _read_message()
        if request is None:
            return 0
        method = request.get("method")
        request_id = request.get("id")
        params = request.get("params") or {}
        result: Any = None
        if method == "initialize":
            result = {
                "serverInfo": {"name": "reasonscript-lsp", "version": "0.1"},
                "capabilities": {
                    "textDocumentSync": 1,
                    "hoverProvider": True,
                    "completionProvider": {"triggerCharacters": ["."]},
                    "definitionProvider": True,
                    "documentSymbolProvider": True,
                    "referencesProvider": True,
                    "workspaceSymbolProvider": True,
                    "codeActionProvider": {"codeActionKinds": ["quickfix"]},
                    "signatureHelpProvider": {"triggerCharacters": ["(", ","]},
                    "semanticTokensProvider": {
                        "legend": SEMANTIC_TOKENS_LEGEND.to_dict(),
                        "full": True,
                    },
                    "renameProvider": {"prepareProvider": True},
                    "documentFormattingProvider": True,
                },
                "metadata": {"schema": server.schema},
            }
        elif method == "textDocument/didOpen":
            item = params["textDocument"]
            state = server.open_document(item["uri"], item.get("text", ""), int(item.get("version", 1)))
            _publish_diagnostics(item["uri"], state.diagnostics)
            continue
        elif method == "textDocument/didChange":
            item = params["textDocument"]
            changes = params.get("contentChanges", [])
            text = changes[-1].get("text", "") if changes else ""
            state = server.change_document(item["uri"], text, int(item.get("version", 1)))
            _publish_diagnostics(item["uri"], state.diagnostics)
            continue
        elif method == "textDocument/diagnostic":
            uri = params["textDocument"]["uri"]
            result = {"items": [_diagnostic_json(item) for item in server.diagnostics(uri)]}
        elif method == "textDocument/documentSymbol":
            uri = params["textDocument"]["uri"]
            symbols = server.document_symbols(uri)
            result = [s.to_dict() for s in symbols]
        elif method == "textDocument/codeAction":
            uri = params["textDocument"]["uri"]
            rng_dict = params.get("range", {})
            start = rng_dict.get("start", {})
            end = rng_dict.get("end", {})
            req_rng = Range(
                Position(int(start.get("line", 0)), int(start.get("character", 0))),
                Position(int(end.get("line", 0)), int(end.get("character", 0))),
            )
            actions = server.code_actions(uri, req_rng)
            result = [action.to_dict() for action in actions]
        elif method == "textDocument/hover":
            uri, line, character = _position(params)
            hover = server.hover(uri, line, character)
            if hover is None:
                result = None
            elif isinstance(hover.contents, str):
                result = {"contents": {"kind": "markdown", "value": hover.contents}}
            else:
                result = {"contents": hover.contents}
        elif method == "textDocument/completion":
            uri, line, character = _position(params)
            result = [
                {
                    "label": item.label,
                    "kind": item.kind,
                    "detail": item.detail,
                    "documentation": {"kind": "markdown", "value": item.documentation} if item.documentation else None,
                }
                for item in server.completion(uri, line, character)
            ]
        elif method == "textDocument/definition":
            uri, line, character = _position(params)
            location = server.definition(uri, line, character)
            result = None if location is None else _location_json(location)
        elif method == "textDocument/references":
            uri, line, character = _position(params)
            result = [_location_json(item) for item in server.references(uri, line, character)]
        elif method == "textDocument/signatureHelp":
            uri, line, character = _position(params)
            sig_help = server.signature_help(uri, line, character)
            result = sig_help.to_dict() if sig_help is not None else None
        elif method == "textDocument/semanticTokens/full":
            uri = params["textDocument"]["uri"]
            tokens = server.semantic_tokens(uri)
            result = tokens.to_dict() if tokens is not None else {"data": []}
        elif method == "textDocument/prepareRename":
            uri, line, character = _position(params)
            rng = server.prepare_rename(uri, line, character)
            result = _range_json(rng) if rng is not None else None
        elif method == "textDocument/rename":
            uri, line, character = _position(params)
            new_name = params.get("newName", "")
            edit = server.rename(uri, line, character, new_name)
            result = edit.to_dict() if edit is not None else None
        elif method == "textDocument/formatting":
            uri = params["textDocument"]["uri"]
            options_dict = params.get("options", {})
            options = FormattingOptions(
                tab_size=int(options_dict.get("tabSize", 4)),
                insert_spaces=bool(options_dict.get("insertSpaces", True)),
            )
            edits = server.formatting(uri, options)
            result = [e.to_dict() for e in edits]
        elif method == "workspace/symbol":
            query = params.get("query", "")
            result = [
                {
                    "name": item.name,
                    "kind": SYMBOL_KIND_MAP.get(item.kind, 1),
                    "location": _location_json(item.location),
                    "containerName": item.module,
                }
                for item in server.workspace_symbols(query)
            ]
        elif method == "$/cancelRequest":
            continue
        elif method == "shutdown":
            result = None
        elif method == "exit":
            return 0
        if request_id is not None:
            _send({"jsonrpc": "2.0", "id": request_id, "result": result})


def _diagnostic_json(diagnostic: Any) -> dict[str, Any]:
    sev = 1
    if hasattr(diagnostic, "severity"):
        if diagnostic.severity == DiagnosticSeverity.WARNING:
            sev = 2
        elif diagnostic.severity == DiagnosticSeverity.INFORMATION:
            sev = 3
        elif diagnostic.severity == DiagnosticSeverity.HINT:
            sev = 4
    res = {
        "range": _range_json(diagnostic.location.range),
        "severity": sev,
        "code": diagnostic.code,
        "message": diagnostic.message,
        "source": "reasonscript-lsp",
    }
    if getattr(diagnostic, "data", None) is not None:
        res["data"] = diagnostic.data
    return res


def _location_json(location: Any) -> dict[str, Any]:
    return {"uri": location.uri, "range": _range_json(location.range)}


def _range_json(range_value: Any) -> dict[str, Any]:
    return {
        "start": {"line": range_value.start.line, "character": range_value.start.character},
        "end": {"line": range_value.end.line, "character": range_value.end.character},
    }
