"""The Playground backend only serves local IDE pages and local artifact paths."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

from playground.backend import main
from playground.backend.security import is_allowed_origin


class _AsgiClient:
    """Minimal in-process ASGI client; the dev requirements do not ship httpx."""

    def request(self, method: str, path: str, *, json_body=None, headers=None):
        body = b"" if json_body is None else json.dumps(json_body).encode("utf-8")
        raw_headers = [(b"host", b"127.0.0.1:8000"), (b"content-type", b"application/json"),
                       (b"content-length", str(len(body)).encode("ascii"))]
        raw_headers += [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()]
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
                 "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"",
                 "root_path": "", "headers": raw_headers, "client": ("127.0.0.1", 50000),
                 "server": ("127.0.0.1", 8000)}
        messages = [{"type": "http.request", "body": body, "more_body": False}]
        sent: list[dict] = []

        async def receive():
            return messages.pop(0) if messages else {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        asyncio.run(main.app(scope, receive, send))
        start = next(item for item in sent if item["type"] == "http.response.start")
        text = b"".join(item.get("body", b"") for item in sent if item["type"] == "http.response.body").decode()
        response_headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in start["headers"]}
        return SimpleNamespace(status_code=start["status"], text=text, headers=response_headers,
                               json=lambda: json.loads(text))

    def post(self, path, *, json=None, headers=None):
        return self.request("POST", path, json_body=json, headers=headers)

    def options(self, path, *, headers=None):
        return self.request("OPTIONS", path, headers=headers)


@pytest.fixture()
def client() -> _AsgiClient:
    return _AsgiClient()


def _workspace(tmp_path):
    (tmp_path / "secret.txt").write_text("secret\n", encoding="utf-8")
    return str(tmp_path)


@pytest.mark.parametrize("origin", [
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://[::1]:5173",
    "tauri://localhost",
    "http://tauri.localhost",
])
def test_local_origins_are_allowed(origin):
    assert is_allowed_origin(origin)


@pytest.mark.parametrize("origin", [
    "https://evil.example",
    "http://localhost.evil.example",
    "http://127.0.0.1.evil.example:8000",
    "null",
])
def test_remote_origins_are_rejected(origin):
    assert not is_allowed_origin(origin)


def test_cross_origin_workspace_read_is_forbidden(client, tmp_path):
    response = client.post(
        "/api/workspace/read",
        json={"workspace_root": _workspace(tmp_path), "relative_path": "secret.txt"},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403
    assert "secret" not in response.text


def test_cross_origin_workspace_save_does_not_write(client, tmp_path):
    root = _workspace(tmp_path)
    response = client.post(
        "/api/workspace/save",
        json={"workspace_root": root, "relative_path": "planted.txt", "content": "x"},
        headers={"Origin": "http://attacker.test"},
    )

    assert response.status_code == 403
    assert not (tmp_path / "planted.txt").exists()


def test_cors_preflight_from_remote_origin_is_not_granted(client):
    response = client.options(
        "/api/workspace/read",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )

    assert response.headers.get("access-control-allow-origin") is None


def test_local_ide_origin_can_read_workspace(client, tmp_path):
    response = client.post(
        "/api/workspace/read",
        json={"workspace_root": _workspace(tmp_path), "relative_path": "secret.txt"},
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    assert response.json()["content"] == "secret\n"
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_import_rejects_paths_outside_artifact_directories(client, tmp_path):
    (tmp_path / "manifest.json").write_text('{"leak": true}', encoding="utf-8")

    response = client.post("/api/import", json={"path": str(tmp_path)})

    assert response.json()["ok"] is False
    assert "manifest" not in response.json()


def test_diff_rejects_paths_outside_artifact_directories(client, tmp_path):
    response = client.post("/api/diff", json={"a": str(tmp_path), "b": {}})

    assert response.json()["ok"] is False
