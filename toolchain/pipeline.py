"""Shared compilation pipeline used by build, run, check, and test commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from frontend.computation_ir import LoweringError
from frontend.language_surface.integration import compile_program, project_program
from frontend.language_surface.namespace import NamespaceResolutionError
from frontend.language_surface.nodes import ProgramNode
from frontend.language_surface.parser import SurfaceSyntaxError, parse, parse_unresolved
from frontend.language_surface.validation import SurfaceValidationError


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
        ir_metadata = ir.get("metadata", {})
        return {
            "package": ir.get("package", ir_metadata.get("package")),
            "module": ir.get("module", ir_metadata.get("module")),
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


def compile_package_sources(sources: list[tuple[str, Path]]) -> PipelineResult:
    """Compile every source in a package as one closed module graph."""
    program = _package_program(sources)
    try:
        reason_irs = compile_program(program)
    except (SurfaceValidationError, NamespaceResolutionError) as e:
        raise PipelineError("ValidationError", str(e)) from e
    except Exception as e:
        raise PipelineError("CompilerError", str(e)) from e
    return PipelineResult(sources[0][1], program, reason_irs)


def validate_package_sources(
    sources: list[tuple[str, Path]], *, require_executable: bool = False
) -> None:
    """Validate every source against the complete module graph.

    ``require_executable`` adds the exact optimized Computation IR lowering
    and validation used by ``reason build``.  Keeping that work in one helper
    is the executable-check contract: a default check and a build cannot
    silently disagree about IR support.
    """
    program = _package_program(sources)
    try:
        project_program(program)
        if require_executable:
            lower_executable_program(program)
    except (SurfaceValidationError, NamespaceResolutionError) as e:
        raise PipelineError("ValidationError", str(e)) from e
    except LoweringError as e:
        raise PipelineError(e.code, _lowering_message(e)) from e
    except Exception as e:
        raise PipelineError("CompilerError", str(e)) from e


def lower_executable_program(program: ProgramNode) -> dict[str, Any]:
    """Produce the canonical executable IR shared by check and build."""
    from frontend.computation_ir import lower_program, validate_program
    from frontend.computation_ir.optimizer import optimize_program

    computation_ir = optimize_program(lower_program(program))
    validation_errors = validate_program(computation_ir)
    if validation_errors:
        raise LoweringError("IR-LOWER-010", "; ".join(validation_errors))
    return computation_ir


def _lowering_message(error: Exception) -> str:
    code = getattr(error, "code", "")
    message = str(error)
    prefix = f"{code}: "
    return message[len(prefix):] if code and message.startswith(prefix) else message


def _package_program(sources: list[tuple[str, Path]]) -> ProgramNode:
    if not sources:
        raise PipelineError("SyntaxError", "package has no source files")
    try:
        units = [parse_unresolved(source) for source, _path in sources]
        packages = {unit.package.name for unit in units if unit.package is not None}
        if len(packages) > 1:
            raise PipelineError(
                "SyntaxError", "PV-2 package declaration conflicts across source files"
            )
        package = next((unit.package for unit in units if unit.package is not None), None)
        program = ProgramNode(
            tuple(module for unit in units for module in unit.modules), package
        )
        from frontend.language_surface.namespace import resolve_program
        from frontend.language_surface.validation import validate

        program, _ = resolve_program(program)
        validate(program)
        return program
    except PipelineError:
        raise
    except SurfaceSyntaxError as e:
        raise PipelineError("SyntaxError", str(e)) from e
    except (SurfaceValidationError, NamespaceResolutionError) as e:
        raise PipelineError("ValidationError", str(e)) from e
