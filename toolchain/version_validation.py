"""Release version consistency validation."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "reasonscript-version-validation/1.0"
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:\.(0|[1-9]\d*))?"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


def validate_version(root: Path, *, tag: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    checks: list[dict[str, str]] = []
    try:
        canonical = (root / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        canonical = ""
    _add(checks, "VER-001", canonical, canonical, bool(SEMVER.fullmatch(canonical)))

    pyproject = _toml(root / "pyproject.toml")
    release = _json(root / "metadata" / "release_manifest.json")
    _add(checks, "VER-002", str(pyproject.get("project", {}).get("version", "")), canonical)
    _add(checks, "VER-003", str(release.get("reason_version", "")), canonical)
    _add(checks, "VER-004", str(release.get("runtime_version", "")), canonical)
    _add(checks, "VER-005", str(release.get("cli_version", "")), canonical)
    parts = canonical.split(".")
    compatibility = (
        f">={parts[0]}.{parts[1]}.0,<{parts[0]}.{int(parts[1]) + 1}.0"
        if len(parts) in {3, 4} and parts[1].isdigit()
        else ""
    )
    _add(checks, "VER-006", str(release.get("runtime_compatibility", "")), compatibility)
    version_token = canonical.replace(".", "_")
    readme = _text(root / "README.md")
    docs_index = _text(root / "docs" / "README.md")
    changelog = _text(root / "CHANGELOG.md")
    _add(
        checks,
        "VER-007",
        _match(readme, r"Current release: \*\*v([^*]+)\*\*"),
        canonical,
    )
    installation_path = f"docs/installation/ReasonScript_v{version_token}_Installation.md"
    _add(checks, "VER-008", installation_path if installation_path in readme else "", installation_path)
    docs_installation = f"installation/ReasonScript_v{version_token}_Installation.md"
    _add(checks, "VER-009", docs_installation if docs_installation in docs_index else "", docs_installation)
    if tag is not None:
        _add(checks, "VER-010", tag.removeprefix("v"), canonical)
    changelog_heading = f"## v{canonical}"
    _add(checks, "VER-011", changelog_heading if changelog_heading in changelog else "", changelog_heading)
    release_notes = root / "release" / f"RELEASE_NOTES_v{version_token}.md"
    release_title = f"ReasonScript {canonical}"
    _add(
        checks,
        "VER-012",
        release_title if release_title in _text(release_notes) else "",
        release_title,
    )
    failed = sum(item["status"] == "fail" for item in checks)
    return {"schema_version": SCHEMA_VERSION, "status": "pass" if not failed else "fail",
            "canonical_version": canonical, "checks": checks,
            "summary": {"passed": len(checks) - failed, "failed": failed}}


def command(args: list[str], root: Path | None = None) -> int:
    root = (root or Path.cwd()).resolve()
    tag = _option(args, "--tag")
    if "--tag-current" in args:
        proc = subprocess.run(["git", "describe", "--tags", "--exact-match"], cwd=root, text=True, capture_output=True)
        tag = proc.stdout.strip() if proc.returncode == 0 else ""
    payload = validate_version(root, tag=tag)
    if "--json" in args:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Version validation: {payload['status']}")
        for check in payload["checks"]:
            print(f"[{check['status'].upper()}] {check['id']}: {check['actual']} (expected {check['expected']})")
    return 0 if payload["status"] == "pass" else 1


def _add(checks: list[dict[str, str]], ident: str, actual: str, expected: str, ok: bool | None = None) -> None:
    checks.append({"id": ident, "status": "pass" if (actual == expected if ok is None else ok) else "fail",
                   "actual": actual, "expected": expected})


def _toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _match(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    return match.group(1) if match else ""


def _option(args: list[str], name: str) -> str | None:
    if name not in args or args.index(name) + 1 >= len(args):
        return None
    return args[args.index(name) + 1]
