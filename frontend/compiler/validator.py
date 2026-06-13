from __future__ import annotations

from typing import Any, Mapping

from frontend.ast import AstValidationError, ModuleNode, to_json_value, validate
from frontend.ast_validator import AstDocumentError, validate_document

from .errors import CompilerError, CompilerErrorCode


def validate_ast(module: ModuleNode) -> ModuleNode:
    if not isinstance(module, ModuleNode):
        raise CompilerError(
            CompilerErrorCode.INVALID_AST,
            getattr(module, "node_id", None),
            "compiler input must be ModuleNode",
        )
    try:
        validate(module)
    except AstValidationError as error:
        raise CompilerError(
            CompilerErrorCode.INVALID_AST, module.node_id, str(error)
        ) from error
    try:
        validate_document(to_json_value(module))
    except AstDocumentError as error:
        raise CompilerError(
            CompilerErrorCode.SCHEMA_VIOLATION, module.node_id, str(error)
        ) from error
    return module


def require_ast_document(value: Mapping[str, Any]) -> None:
    for node in value.get("declarations", ()):
        if isinstance(node, Mapping) and node.get("node_type") not in {
            "GoalNode",
            "StateNode",
            "TransitionNode",
            "ConstraintNode",
            "ContextNode",
        }:
            raise CompilerError(
                CompilerErrorCode.UNSUPPORTED_NODE,
                node.get("node_id"),
                f"unsupported node_type: {node.get('node_type')}",
            )
    try:
        validate_document(value)
    except AstDocumentError as error:
        node_id = value.get("node_id") if isinstance(value, Mapping) else None
        raise CompilerError(
            CompilerErrorCode.SCHEMA_VIOLATION, node_id, str(error)
        ) from error
