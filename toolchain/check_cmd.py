"""reason check — validate sources without building runtime artifacts."""

from __future__ import annotations

from pathlib import Path

from .diagnostics import (
    Diagnostic,
    _is_known_code,
    diagnostic_from_parts,
    diagnostics_document,
    stable_json,
)
from .manifest import Manifest, ManifestError
from .pipeline import PipelineError, validate_package_sources
from .source_selection import SourceSelectionError, package_sources
from .workspace import (
    PackageGraphService,
    WorkspaceError,
    diagnostic_from_workspace_error,
)


def run(project_root: Path, package: str | None = None, diagnostic_format: str = "text") -> int:
    is_json = diagnostic_format == "json"
    try:
        workspace = PackageGraphService().discover(project_root)
    except WorkspaceError as error:
        if is_json:
            diag = diagnostic_from_workspace_error(error)
            print(stable_json(diagnostics_document([diag])), end="")
        else:
            _print_workspace_error(error)
        return 1
    except ManifestError as error:
        if is_json:
            diag = diagnostic_from_parts(code="PRJ-0001", message=str(error), file=str(project_root / "reason.toml"), severity="ERROR")
            print(stable_json(diagnostics_document([diag])), end="")
        else:
            print(f"Error:\n\n{error}")
        return 1

    if workspace.is_workspace:
        package_names = (package,) if package is not None else workspace.graph.build_order
        checked = 0
        for package_name in package_names:
            try:
                node = workspace.graph.package(package_name)
            except WorkspaceError as error:
                if is_json:
                    diag = diagnostic_from_workspace_error(error)
                    print(stable_json(diagnostics_document([diag])), end="")
                else:
                    _print_workspace_error(error)
                return 1
            rc = _run_package(node.path, is_json)
            if rc != 0:
                return rc
            checked += 1
        if is_json:
            print(stable_json(diagnostics_document([])), end="")
        else:
            print(f"Workspace check passed. {checked} package(s) validated.")
        return 0

    if package is not None and package != workspace.default_package.name:
        error = WorkspaceError(f"unknown package: {package}")
        if is_json:
            diag = diagnostic_from_workspace_error(error)
            print(stable_json(diagnostics_document([diag])), end="")
        else:
            _print_workspace_error(error)
        return 1
    return _run_package(workspace.default_package.path, is_json)


def _run_package(project_root: Path, is_json: bool = False) -> int:
    try:
        manifest = Manifest.load(project_root)
    except ManifestError as e:
        if is_json:
            diag = diagnostic_from_parts(code="PRJ-0001", message=str(e), file=str(project_root / "reason.toml"), severity="ERROR")
            print(stable_json(diagnostics_document([diag])), end="")
        else:
            print(f"Error:\n\n{e}")
        return 1

    try:
        sources = package_sources(project_root, manifest)
    except SourceSelectionError as error:
        if is_json:
            code = error.code if _is_known_code(error.code) else "SRC-0001"
            diag = diagnostic_from_parts(code=code, message=str(error), file="src", severity="ERROR")
            print(stable_json(diagnostics_document([diag])), end="")
        else:
            print(f"Error:\n\n{error.code}\n\n{error}")
        return 1
    if not sources:
        if is_json:
            diag = diagnostic_from_parts(code="SRC-0002", message="No .rsn files found in src/.", file="src", severity="ERROR")
            print(stable_json(diagnostics_document([diag])), end="")
        else:
            print("Error:\n\nNoSourceFiles\n\nNo .rsn files found in src/.")
        return 1

    try:
        validate_package_sources(
            [(src_path.read_text(encoding="utf-8"), src_path) for src_path in sources]
        )
    except PipelineError as e:
        if is_json:
            code = e.code if _is_known_code(e.code) else "PAR-0001"
            diag = diagnostic_from_parts(code=code, message=e.message, file="src", severity="ERROR")
            print(stable_json(diagnostics_document([diag])), end="")
        else:
            print(f"Error:\n\n{e.code}: {e.message}")
        return 1

    if is_json:
        print(stable_json(diagnostics_document([])), end="")
    else:
        print(f"Check passed. {len(sources)} file(s) validated.")
    return 0


def _print_workspace_error(error: WorkspaceError) -> None:
    diagnostic = diagnostic_from_workspace_error(error)
    print(f"Error:\n\n{diagnostic.code}\n\n{diagnostic.message}")
