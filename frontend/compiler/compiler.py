from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from conformance.framework import ConformanceError
from conformance.schema_validator import SchemaValidator
from frontend.ast import ModuleNode, from_json_value

from .errors import CompilerError, CompilerErrorCode
from .expander import expand_defaults
from .injector import CompilationPolicies, inject_policies
from .lowering import lower
from .validator import require_ast_document, validate_ast

ROOT = Path(__file__).resolve().parents[2]


def compile(
    ast: ModuleNode, policies: CompilationPolicies | None = None
) -> dict[str, Any]:
    validated = validate_ast(ast)
    expanded = expand_defaults(validated)
    context = inject_policies(policies)
    reason_ir = lower(expanded, context)
    try:
        SchemaValidator(ROOT / "schemas").validate_file(
            reason_ir, "reason_ir.schema.json"
        )
    except ConformanceError as error:
        raise CompilerError(
            CompilerErrorCode.LOWERING_FAILURE, ast.node_id, str(error)
        ) from error
    return reason_ir


def compile_document(
    value: Mapping[str, Any], policies: CompilationPolicies | None = None
) -> dict[str, Any]:
    require_ast_document(value)
    try:
        ast = from_json_value(value)
    except (KeyError, TypeError, ValueError) as error:
        raise CompilerError(
            CompilerErrorCode.INVALID_AST, value.get("node_id"), str(error)
        ) from error
    return compile(ast, policies)
