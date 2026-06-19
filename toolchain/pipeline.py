"""Shared compilation pipeline used by build, run, check, and test commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from frontend.language_surface.parser import SurfaceSyntaxError, parse
from frontend.language_surface.validation import SurfaceValidationError
from frontend.language_surface.namespace import NamespaceResolutionError
from frontend.language_surface.integration import compile_program, project_program


class PipelineError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class PipelineResult:
    source_path: Path
    surface_ast: Any
    reason_irs: tuple[dict[str, Any], ...]

    def metadata_for(self, ir: dict[str, Any]) -> dict[str, Any]:
        return {
            "package": ir.get("package"),
            "module": ir.get("module"),
            "runtime_calls": ir.get("runtime_calls", []),
            "reasoning_declarations": ir.get("reasoning_declarations", {}),
        }


def compile_source(source: str, path: Path) -> PipelineResult:
    """Run Source → Lexer → Parser → AST → Validation → Semantic AST → Reason IR."""
    try:
        program = parse(source)
    except SurfaceSyntaxError as e:
        raise PipelineError("SyntaxError", str(e)) from e

    try:
        reason_irs = compile_program(program)
    except (SurfaceValidationError, NamespaceResolutionError) as e:
        raise PipelineError("ValidationError", str(e)) from e
    except Exception as e:
        raise PipelineError("CompilerError", str(e)) from e

    return PipelineResult(
        source_path=path,
        surface_ast=program,
        reason_irs=reason_irs,
    )


def validate_source(source: str, _path: Path) -> None:
    """Run Lexer → Parser → Validation → Semantic Validation only (no IR)."""
    try:
        program = parse(source)
    except SurfaceSyntaxError as e:
        raise PipelineError("SyntaxError", str(e)) from e

    try:
        project_program(program)
    except (SurfaceValidationError, NamespaceResolutionError) as e:
        raise PipelineError("ValidationError", str(e)) from e
    except Exception as e:
        raise PipelineError("CompilerError", str(e)) from e
