"""Regression contract tests for the ReasonScript VS Code extension.

Validates that:
1. Document selector is locked to language 'reasonscript', scheme 'file', pattern '**/*.rsn'.
2. Activation events only target ReasonScript ('onLanguage:reasonscript') and do not intercept '.re'/'.res'.
3. Automatically launches 'reason lsp --stdio'.
4. Server restart command 'reasonscript.restartServer' is defined and implemented.
5. Error / Crash handling provides actionable guidance (Restart Server, Open Settings).
6. TypeScript static check passes.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

REPO_ROOT = Path(__file__).resolve().parents[2]
EXTENSION_DIR = REPO_ROOT / "vscode-extension"
PACKAGE_JSON = EXTENSION_DIR / "package.json"
CLIENT_TS = EXTENSION_DIR / "src" / "lsp" / "client.ts"
WORKSPACE_TS = EXTENSION_DIR / "src" / "workspace" / "workspace.ts"
EXTENSION_TS = EXTENSION_DIR / "src" / "extension.ts"


def test_package_json_languages_locked_to_rsn() -> None:
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    languages = data.get("contributes", {}).get("languages", [])
    assert len(languages) == 1, "Expected exactly 1 language contribution"
    lang = languages[0]
    assert lang.get("id") == "reasonscript"
    extensions = lang.get("extensions", [])
    assert extensions == [".rsn"], f"Extensions must be exactly ['.rsn'], got: {extensions}"

    # Foreign / legacy extensions must not be present
    forbidden = {".re", ".rei", ".res", ".resi", ".ml", ".mli"}
    for ext in forbidden:
        assert ext not in extensions, f"Forbidden extension '{ext}' present in language configuration"


def test_package_json_activation_events_do_not_contain_foreign_extensions() -> None:
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    activation = data.get("activationEvents", [])
    assert "onLanguage:reasonscript" in activation
    assert "onCommand:reasonscript.restartServer" in activation

    import re

    # Activation events must not target foreign languages or extensions (e.g. onLanguage:reason, *.re)
    for event in activation:
        assert not re.search(r"onLanguage:(reason\b|rescript\b)", event, re.IGNORECASE)
        assert not re.search(r"\.(re|rei|res|resi)$", event)


def test_package_json_defines_restart_server_command() -> None:
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    commands = data.get("contributes", {}).get("commands", [])
    command_ids = {cmd["command"] for cmd in commands}
    assert "reasonscript.restartServer" in command_ids


def test_lsp_client_document_selector_and_stdio_args() -> None:
    client_code = CLIENT_TS.read_text(encoding="utf-8")

    # Document selector must target reasonscript with file scheme and **/*.rsn pattern
    assert 'language: "reasonscript"' in client_code
    assert 'scheme: "file"' in client_code
    assert 'pattern: "**/*.rsn"' in client_code

    # Server args must launch reason lsp --stdio
    assert 'args: ["lsp", "--stdio"]' in client_code

    # Error / crash handling must be present
    assert "errorHandler" in client_code
    assert "Restart Server" in client_code
    assert "Open Settings" in client_code


def test_workspace_and_extension_actionable_executable_handling() -> None:
    workspace_code = WORKSPACE_TS.read_text(encoding="utf-8")
    assert "resolveReasonExecutable" in workspace_code
    assert "findOnPath" in workspace_code

    extension_code = EXTENSION_TS.read_text(encoding="utf-8")
    assert "reasonscript.restartServer" in extension_code
    assert "ReasonScript executable not found" in extension_code
    assert "Open Settings" in extension_code


def test_vscode_extension_typescript_compiles_cleanly() -> None:
    result = subprocess.run(
        ["npm", "run", "check"],
        cwd=EXTENSION_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"tsc check failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
