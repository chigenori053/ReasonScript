"""Minimal stdio JSON-RPC transport for ReasonScript LSP Phase 1."""

from __future__ import annotations

import json
import sys
from typing import Any

from .core import ReasonScriptLanguageServer


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
                    "referencesProvider": True,
                    "workspaceSymbolProvider": True,
                },
                "metadata": {"schema": server.schema},
            }
        elif method == "textDocument/didOpen":
            item = params["textDocument"]
            server.open_document(item["uri"], item.get("text", ""), int(item.get("version", 1)))
            continue
        elif method == "textDocument/didChange":
            item = params["textDocument"]
            changes = params.get("contentChanges", [])
            text = changes[-1].get("text", "") if changes else ""
            server.change_document(item["uri"], text, int(item.get("version", 1)))
            continue
        elif method == "textDocument/diagnostic":
            uri = params["textDocument"]["uri"]
            result = {"items": [_diagnostic_json(item) for item in server.diagnostics(uri)]}
        elif method == "textDocument/hover":
            uri, line, character = _position(params)
            hover = server.hover(uri, line, character)
            result = None if hover is None else {"contents": hover.contents}
        elif method == "textDocument/completion":
            uri, line, character = _position(params)
            result = [
                {"label": item.label, "kind": item.kind, "detail": item.detail}
                for item in server.completion(uri, line, character)
            ]
        elif method == "textDocument/definition":
            uri, line, character = _position(params)
            location = server.definition(uri, line, character)
            result = None if location is None else _location_json(location)
        elif method == "textDocument/references":
            uri, line, character = _position(params)
            result = [_location_json(item) for item in server.references(uri, line, character)]
        elif method == "workspace/symbol":
            query = params.get("query", "")
            result = [
                {
                    "name": item.name,
                    "kind": item.kind,
                    "location": _location_json(item.location),
                    "containerName": item.module,
                }
                for item in server.workspace_symbols()
                if query in item.name
            ]
        elif method == "shutdown":
            result = None
        elif method == "exit":
            return 0
        if request_id is not None:
            _send({"jsonrpc": "2.0", "id": request_id, "result": result})


def _diagnostic_json(diagnostic: Any) -> dict[str, Any]:
    return {
        "range": _range_json(diagnostic.location.range),
        "severity": 1,
        "code": diagnostic.code,
        "message": diagnostic.message,
        "source": "reasonscript-lsp",
    }


def _location_json(location: Any) -> dict[str, Any]:
    return {"uri": location.uri, "range": _range_json(location.range)}


def _range_json(range_value: Any) -> dict[str, Any]:
    return {
        "start": {"line": range_value.start.line, "character": range_value.start.character},
        "end": {"line": range_value.end.line, "character": range_value.end.character},
    }
