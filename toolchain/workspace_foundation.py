"""Workspace Foundation indexing for ReasonScript projects.

This module implements the reasonscript-workspace/1.0 project model.  It is
kept separate from the existing multi-package toolchain workspace graph so
legacy build/run/check behavior can remain unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

from toolchain.diagnostics import diagnostics_document, diagnostics_summary as canonical_diagnostics_summary


WORKSPACE_SCHEMA = "reasonscript-workspace/1.0"
SUPPORTED_SOURCE_EXTENSIONS = {".rsn", ".rs", ".py", ".toml", ".md", ".json", ".yaml", ".yml"}
IGNORED_DIRECTORIES = {
    ".git",
    "target",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".venv",
    "venv",
}
CANONICAL_DIRECTORIES = ("src", "examples", "tests", "artifacts", "docs", "scripts", ".github")
SUPPORTED_LANGUAGES = {"0.5", "0.7"}
SUPPORTED_WORKSPACE_VERSION = "1.0"
GENERATED_ARTIFACTS = (
    "workspace.json",
    "project_summary.json",
    "symbol_index.json",
    "dependency_graph.json",
    "diagnostics.json",
    "diagnostics_summary.json",
    "workspace_validation.json",
)


_SYMBOL_PATTERN = re.compile(
    r"^\s*(?P<kind>module|model|fn|function|struct|enum|calculation|goal|state|constraint)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_IMPORT_PATTERN = re.compile(r"^\s*(?:import|use)\s+(?P<target>[A-Za-z_][A-Za-z0-9_.]*)")
_RUNTIME_PATTERN = re.compile(r"\bruntime\.([A-Za-z_][A-Za-z0-9_]*)")
_IDENTIFIER_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9_]*\b")
_COMMENT_PATTERN = re.compile(r"//.*$")


@dataclass(frozen=True)
class WorkspaceDiagnostic:
    code: str
    message: str
    severity: str = "ERROR"
    file: str | None = None
    line: int | None = None
    column: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "column": self.column,
        }


def build_workspace_index(start: str | Path) -> dict[str, Any]:
    root = Path(start).resolve()
    if root.is_file():
        root = root.parent
    manifest, manifest_diagnostics = _load_project_manifest(root)
    files = _discover_files(root)
    directories = _discover_directories(root)
    symbols = _index_symbols(root, files)
    modules = [symbol for symbol in symbols if symbol["kind"] == "module"]
    dependencies = _build_dependency_graph(root, files, symbols)
    diagnostics = [
        *manifest_diagnostics,
        *_validate_layout(root),
        *_validate_duplicates(symbols),
        *_validate_dependencies(dependencies),
    ]
    diagnostic_document = diagnostics_document([diagnostic.to_dict() for diagnostic in diagnostics])
    artifacts = [{"path": f"artifacts/{name}", "kind": "generated"} for name in GENERATED_ARTIFACTS]
    project_info = {
        "name": manifest.get("name", ""),
        "version": manifest.get("version", ""),
        "language": manifest.get("language", ""),
        "workspace": manifest.get("workspace", ""),
        "authors": manifest.get("authors", []),
        "license": manifest.get("license", ""),
        "description": manifest.get("description", ""),
        "repository": manifest.get("repository", ""),
        "edition": manifest.get("edition", "2026"),
        "runtime": manifest.get("runtime", "default"),
    }
    return {
        "schema": WORKSPACE_SCHEMA,
        "project_info": project_info,
        "directories": directories,
        "files": files,
        "modules": modules,
        "symbols": symbols,
        "dependencies": dependencies,
        "artifacts": artifacts,
        "diagnostics": diagnostic_document["diagnostics"],
    }


def workspace_summary(index: dict[str, Any]) -> dict[str, Any]:
    symbols = index.get("symbols", [])
    counts: dict[str, int] = {}
    for symbol in symbols if isinstance(symbols, list) else []:
        if isinstance(symbol, dict):
            kind = str(symbol.get("kind", ""))
            counts[kind] = counts.get(kind, 0) + 1
    dependencies = index.get("dependencies", {})
    edges = dependencies.get("edges", []) if isinstance(dependencies, dict) else []
    diagnostics = index.get("diagnostics", [])
    return {
        "schema": "reasonscript-project-summary/1.0",
        "project": index.get("project_info", {}).get("name", ""),
        "language": index.get("project_info", {}).get("language", ""),
        "workspace": index.get("project_info", {}).get("workspace", ""),
        "files": len(index.get("files", [])),
        "modules": counts.get("module", 0),
        "functions": counts.get("function", 0),
        "calculations": counts.get("calculation", 0),
        "symbols": len(symbols) if isinstance(symbols, list) else 0,
        "dependencies": len(edges) if isinstance(edges, list) else 0,
        "diagnostics": len(diagnostics) if isinstance(diagnostics, list) else 0,
    }


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_workspace_artifacts(start: str | Path, out_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(start).resolve()
    if root.is_file():
        root = root.parent
    index = build_workspace_index(root)
    target = Path(out_dir).resolve() if out_dir is not None else root / "artifacts"
    summary = workspace_summary(index)
    diagnostic_document = {
        "version": "1.0",
        "schema": "reasonscript-diagnostics/1.0",
        "diagnostics": index["diagnostics"],
    }
    symbol_index = {
        "schema": "reasonscript-symbol-index/1.0",
        "symbols": index["symbols"],
        "diagnostics": [
            diagnostic for diagnostic in index["diagnostics"]
            if diagnostic.get("code") in {"WS-003", "WS-004"}
        ],
    }
    dependency_graph = index["dependencies"]
    validation = {
        "schema": "reasonscript-workspace-validation/1.0",
        "ok": not any(diagnostic.get("severity") == "ERROR" for diagnostic in index["diagnostics"]),
        "diagnostics": index["diagnostics"],
    }
    outputs = {
        "workspace.json": index,
        "project_summary.json": summary,
        "symbol_index.json": symbol_index,
        "dependency_graph.json": dependency_graph,
        "diagnostics.json": diagnostic_document,
        "diagnostics_summary.json": canonical_diagnostics_summary(diagnostic_document),
        "workspace_validation.json": validation,
    }
    if target.exists() and not target.is_dir():
        return {"out_dir": str(target), "artifacts": [], "index": index, "summary": summary}
    target.mkdir(parents=True, exist_ok=True)
    for filename in GENERATED_ARTIFACTS:
        (target / filename).write_text(stable_json(outputs[filename]), encoding="utf-8")
    return {"out_dir": str(target), "artifacts": sorted(outputs), "index": index, "summary": summary}


def _load_project_manifest(root: Path) -> tuple[dict[str, Any], list[WorkspaceDiagnostic]]:
    path = root / "reason.toml"
    diagnostics: list[WorkspaceDiagnostic] = []
    if not path.is_file():
        return {}, [WorkspaceDiagnostic("WS-001", f"Missing project manifest: {path}", file="reason.toml")]
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        return {}, [WorkspaceDiagnostic("WS-002", f"Invalid manifest: {error}", file="reason.toml")]

    if isinstance(data.get("package"), dict):
        package = data["package"]
        compiler = data.get("compiler", {}) if isinstance(data.get("compiler"), dict) else {}
        runtime = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
        manifest = {
            "name": package.get("name"),
            "version": package.get("version"),
            "language": compiler.get("language", compiler.get("language_core", "0.5")),
            "workspace": data.get("workspace", {}).get("version", SUPPORTED_WORKSPACE_VERSION)
            if isinstance(data.get("workspace"), dict) else SUPPORTED_WORKSPACE_VERSION,
            "runtime": runtime.get("name", runtime.get("backend", "default")),
        }
    else:
        manifest = dict(data)

    required = ("name", "version", "language", "workspace")
    for field in required:
        if not isinstance(manifest.get(field), str) or not manifest.get(field):
            diagnostics.append(WorkspaceDiagnostic("WS-002", f"Invalid manifest: missing string field '{field}'", file="reason.toml"))
    language = manifest.get("language")
    workspace_version = manifest.get("workspace")
    if isinstance(language, str) and language not in SUPPORTED_LANGUAGES:
        diagnostics.append(WorkspaceDiagnostic("WS-006", f"Unsupported language version: {language}", file="reason.toml"))
    if isinstance(workspace_version, str) and workspace_version != SUPPORTED_WORKSPACE_VERSION:
        diagnostics.append(
            WorkspaceDiagnostic("WS-007", f"Workspace version mismatch: {workspace_version}", file="reason.toml")
        )
    if manifest.get("authors") is None:
        manifest["authors"] = []
    return manifest, diagnostics


def _discover_directories(root: Path) -> list[dict[str, Any]]:
    directories: list[dict[str, Any]] = []
    for path in _walk_directories(root):
        relative = _relative_path(root, path)
        directories.append({
            "path": relative,
            "kind": _directory_kind(relative),
        })
    return sorted(directories, key=lambda item: item["path"])


def _discover_files(root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in _walk_files(root):
        if path.suffix.lower() not in SUPPORTED_SOURCE_EXTENSIONS:
            continue
        relative = _relative_path(root, path)
        files.append({
            "path": relative,
            "extension": path.suffix.lower(),
            "kind": _file_kind(relative),
            "bytes": path.stat().st_size,
        })
    return sorted(files, key=lambda item: item["path"])


def _walk_directories(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    result: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop(0)
        children = sorted((child for child in current.iterdir() if child.is_dir()), key=lambda item: item.name)
        for child in children:
            if child.name in IGNORED_DIRECTORIES:
                continue
            result.append(child)
            stack.append(child)
    return result


def _walk_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    result: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop(0)
        children = sorted(current.iterdir(), key=lambda item: (not item.is_dir(), item.name))
        for child in children:
            if child.is_dir():
                if child.name not in IGNORED_DIRECTORIES:
                    stack.append(child)
            elif child.is_file():
                result.append(child)
    return result


def _index_symbols(root: Path, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    symbols: list[dict[str, Any]] = []
    for file_info in files:
        relative = str(file_info["path"])
        if Path(relative).suffix.lower() != ".rsn":
            continue
        path = root / relative
        current_module = Path(relative).stem
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = _COMMENT_PATTERN.sub("", raw_line)
            match = _SYMBOL_PATTERN.match(line)
            if match is None:
                continue
            kind = "function" if match.group("kind") in {"fn", "function"} else match.group("kind")
            name = match.group("name")
            if kind == "module":
                current_module = name
            column = match.start("name") + 1
            symbols.append({
                "id": _stable_id(kind, relative, name, line_number, column),
                "name": name,
                "kind": kind,
                "module": current_module,
                "file": relative,
                "line": line_number,
                "column": column,
                "visibility": "public",
            })
    return sorted(symbols, key=lambda item: (item["file"], item["line"], item["column"], item["kind"], item["name"]))


def _build_dependency_graph(root: Path, files: list[dict[str, Any]], symbols: list[dict[str, Any]]) -> dict[str, Any]:
    symbol_names = {symbol["name"] for symbol in symbols}
    symbol_by_name = {symbol["name"]: symbol for symbol in symbols}
    source_by_file = {symbol["file"]: symbol["name"] for symbol in symbols if symbol["kind"] == "module"}
    edges: list[dict[str, Any]] = []
    for file_info in files:
        relative = str(file_info["path"])
        if Path(relative).suffix.lower() != ".rsn":
            continue
        source = source_by_file.get(relative, relative)
        path = root / relative
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = _COMMENT_PATTERN.sub("", raw_line)
            import_match = _IMPORT_PATTERN.match(line)
            if import_match is not None:
                target = import_match.group("target").split(".")[0]
                edges.append(_dependency_edge(source, target, "import", relative, line_number))
            for runtime_match in _RUNTIME_PATTERN.finditer(line):
                edges.append(_dependency_edge(source, f"runtime.{runtime_match.group(1)}", "runtime", relative, line_number))
            for target in sorted(set(_IDENTIFIER_PATTERN.findall(line)) & symbol_names):
                if target == source:
                    continue
                target_symbol = symbol_by_name[target]
                if target_symbol["file"] == relative and target_symbol["line"] == line_number:
                    continue
                kind = "calculation" if target_symbol["kind"] == "calculation" else "module"
                edges.append(_dependency_edge(source, target, kind, relative, line_number))
    unique = {(edge["source"], edge["target"], edge["kind"], edge["file"], edge["line"]): edge for edge in edges}
    graph_edges = sorted(unique.values(), key=lambda item: (item["source"], item["target"], item["kind"], item["file"], item["line"]))
    cycles = _find_cycles(graph_edges)
    defined_nodes = sorted({symbol["name"] for symbol in symbols} | set(source_by_file.values()))
    return {
        "schema": "reasonscript-dependency-graph/1.0",
        "defined_nodes": defined_nodes,
        "nodes": sorted({edge["source"] for edge in graph_edges} | {edge["target"] for edge in graph_edges}),
        "edges": graph_edges,
        "cycles": cycles,
    }


def _dependency_edge(source: str, target: str, kind: str, file: str, line: int) -> dict[str, Any]:
    return {
        "id": _stable_id("dependency", source, target, kind, file, line),
        "source": source,
        "target": target,
        "kind": kind,
        "file": file,
        "line": line,
    }


def _find_cycles(edges: list[dict[str, Any]]) -> list[list[str]]:
    graph: dict[str, set[str]] = {}
    for edge in edges:
        graph.setdefault(str(edge["source"]), set()).add(str(edge["target"]))
        graph.setdefault(str(edge["target"]), set())
    cycles: set[tuple[str, ...]] = set()
    for start in sorted(graph):
        _visit_cycle(start, start, graph, [], cycles)
    return [list(cycle) for cycle in sorted(cycles)]


def _visit_cycle(
    start: str,
    current: str,
    graph: dict[str, set[str]],
    path: list[str],
    cycles: set[tuple[str, ...]],
) -> None:
    if current in path:
        return
    path = [*path, current]
    for target in sorted(graph[current]):
        if target == start:
            cycles.add(_canonical_cycle([*path, start]))
        elif target in graph and len(path) < len(graph):
            _visit_cycle(start, target, graph, path, cycles)


def _canonical_cycle(cycle: list[str]) -> tuple[str, ...]:
    body = cycle[:-1]
    rotations = [tuple(body[index:] + body[:index] + [body[index]]) for index in range(len(body))]
    return min(rotations)


def _validate_layout(root: Path) -> list[WorkspaceDiagnostic]:
    diagnostics: list[WorkspaceDiagnostic] = []
    for name in CANONICAL_DIRECTORIES:
        path = root / name
        if path.exists() and not path.is_dir():
            code = "WS-010" if name == "artifacts" else "WS-008"
            diagnostics.append(WorkspaceDiagnostic(code, f"Invalid project layout: {name} must be a directory", file=name))
    return diagnostics


def _validate_duplicates(symbols: list[dict[str, Any]]) -> list[WorkspaceDiagnostic]:
    diagnostics: list[WorkspaceDiagnostic] = []
    modules: dict[str, dict[str, Any]] = {}
    all_symbols: dict[tuple[str, str, str], dict[str, Any]] = {}
    for symbol in symbols:
        if symbol["kind"] == "module":
            previous = modules.get(symbol["name"])
            if previous is not None:
                diagnostics.append(_duplicate_diagnostic("WS-003", "Duplicate module", symbol, previous))
            modules[symbol["name"]] = symbol
        key = (str(symbol.get("module", "")), symbol["kind"], symbol["name"])
        previous = all_symbols.get(key)
        if previous is not None:
            diagnostics.append(_duplicate_diagnostic("WS-004", "Duplicate symbol", symbol, previous))
        all_symbols[key] = symbol
    return diagnostics


def _duplicate_diagnostic(code: str, label: str, symbol: dict[str, Any], previous: dict[str, Any]) -> WorkspaceDiagnostic:
    return WorkspaceDiagnostic(
        code,
        f"{label}: {symbol['name']} also declared at {previous['file']}:{previous['line']}",
        file=str(symbol["file"]),
        line=int(symbol["line"]),
        column=int(symbol["column"]),
    )


def _validate_dependencies(dependencies: dict[str, Any]) -> list[WorkspaceDiagnostic]:
    diagnostics: list[WorkspaceDiagnostic] = []
    nodes = set(dependencies.get("defined_nodes", []))
    for edge in dependencies.get("edges", []):
        target = edge.get("target")
        if isinstance(target, str) and target.startswith("runtime."):
            continue
        if target not in nodes:
            diagnostics.append(
                WorkspaceDiagnostic(
                    "WS-009",
                    f"Broken source reference: {target}",
                    file=edge.get("file"),
                    line=edge.get("line"),
                )
            )
    for cycle in dependencies.get("cycles", []):
        diagnostics.append(WorkspaceDiagnostic("WS-005", f"Circular dependency: {' -> '.join(cycle)}", file="workspace"))
    return diagnostics


def _directory_kind(relative: str) -> str:
    first = relative.split("/", 1)[0]
    if first in CANONICAL_DIRECTORIES:
        return first.lstrip(".")
    return "unknown"


def _file_kind(relative: str) -> str:
    first = relative.split("/", 1)[0]
    if first == "examples":
        return "example"
    if first == "tests":
        return "test"
    if first == "docs":
        return "documentation"
    if first == "artifacts":
        return "artifact"
    if first == "scripts":
        return "script"
    if first == "src":
        return "source"
    return "manifest" if relative == "reason.toml" else "source"


def _relative_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _stable_id(*parts: object) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
