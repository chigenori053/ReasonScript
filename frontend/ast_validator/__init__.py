"""AST ABI schema and semantic validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from conformance.framework import ConformanceError, ROOT, load_json
from conformance.schema_validator import SchemaValidator
from frontend.ast import AstValidationError, from_json_value, validate

SCHEMA_ROOT = ROOT / "frontend" / "schemas"


class AstDocumentError(ValueError):
    """Raised when an AST wire document violates the versioned ABI."""


def validate_document(value: Mapping[str, Any]) -> None:
    try:
        SchemaValidator(SCHEMA_ROOT).validate_file(value, "ast.schema.json")
        validate(from_json_value(value))
    except (ConformanceError, AstValidationError, KeyError, TypeError, ValueError) as error:
        raise AstDocumentError(str(error)) from error


def validate_file(path: str | Path) -> None:
    value = load_json(Path(path))
    if not isinstance(value, Mapping):
        raise AstDocumentError("AST document must be a JSON object")
    validate_document(value)


__all__ = ["AstDocumentError", "validate_document", "validate_file"]
