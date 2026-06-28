"""Semantic resolution for Language Surface patterns."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any, Mapping, TypeAlias

from .namespace import ModuleNamespace, NamespaceResolutionError
from .nodes import (
    BooleanLiteralNode,
    DefaultPatternNode,
    EnumDeclarationNode,
    FloatLiteralNode,
    IdentifierPatternNode,
    IntegerLiteralNode,
    LiteralPatternNode,
    NamedTypeNode,
    NullLiteralNode,
    OrPatternNode,
    Pattern,
    PatternNode,
    PrimitiveKind,
    PrimitiveTypeNode,
    QualifiedPatternNode,
    StringLiteralNode,
    StructDeclarationNode,
    StructBindingPatternNode,
    StructPatternNode,
    TypeNode,
    WildcardPatternNode,
)


class StructPatternSemanticError(ValueError):
    pass


@dataclass(frozen=True)
class SemanticQualifiedPattern:
    namespace: str
    identifier: str


@dataclass(frozen=True)
class SemanticLiteralPattern:
    value: Any
    literal_type: str


@dataclass(frozen=True)
class SemanticWildcardPattern:
    pass


@dataclass(frozen=True)
class SemanticDefaultPattern:
    pass


@dataclass(frozen=True)
class SemanticBindingPattern:
    field_symbol: str
    binding: str


@dataclass(frozen=True)
class SemanticStructFieldPattern:
    field_symbol: str
    field_type: str
    pattern: "SemanticPattern"


@dataclass(frozen=True)
class SemanticStructPattern:
    struct_symbol: str
    fields: tuple[SemanticStructFieldPattern, ...]
    source_span: str | None = None


@dataclass(frozen=True)
class SemanticOrPattern:
    alternatives: tuple["SemanticPattern", ...]


SemanticPattern: TypeAlias = (
    SemanticQualifiedPattern
    | SemanticLiteralPattern
    | SemanticWildcardPattern
    | SemanticDefaultPattern
    | SemanticBindingPattern
    | SemanticStructPattern
    | SemanticOrPattern
)


def resolve_pattern(
    pattern: Pattern | PatternNode,
    expected_type: TypeNode,
    symbols: Mapping[str, Any],
    namespace: ModuleNamespace | None = None,
    *,
    require_complete: bool = False,
) -> SemanticPattern:
    value = pattern.pattern if isinstance(pattern, PatternNode) else pattern
    if isinstance(value, StructPatternNode):
        return _resolve_struct_pattern_for_type(
            value,
            expected_type,
            symbols,
            namespace,
            require_complete=require_complete,
        )
    return _resolve_terminal_pattern(value, expected_type, symbols, namespace)


def resolve_struct_pattern(
    pattern: StructPatternNode,
    symbols: Mapping[str, Any],
    namespace: ModuleNamespace | None = None,
    *,
    require_complete: bool = False,
) -> SemanticStructPattern:
    struct_symbol, declaration = _resolve_struct(pattern.type_name, symbols, namespace)
    declared_fields = {field.name: field for field in declaration.fields}
    resolved_fields: list[SemanticStructFieldPattern] = []
    seen_source: set[str] = set()
    seen_semantic: set[str] = set()
    seen_bindings: set[str] = set()

    for field in pattern.fields:
        if field.field_name in seen_source:
            raise StructPatternSemanticError("SP-103 duplicate struct field")
        seen_source.add(field.field_name)
        declaration_field = declared_fields.get(field.field_name)
        if declaration_field is None:
            raise StructPatternSemanticError("SP-102 unknown struct field")
        if declaration_field.name in seen_semantic:
            raise StructPatternSemanticError("SP-106 duplicate semantic field symbol")
        seen_semantic.add(declaration_field.name)
        semantic_pattern = resolve_pattern(
            field.pattern,
            declaration_field.field_type,
            symbols,
            namespace,
            require_complete=require_complete,
        )
        for binding in _binding_names(semantic_pattern):
            if binding in seen_bindings:
                raise StructPatternSemanticError("SPM-005 duplicate binding name")
            seen_bindings.add(binding)
        resolved_fields.append(
            SemanticStructFieldPattern(
                declaration_field.name,
                _type_symbol(declaration_field.field_type),
                semantic_pattern,
            )
        )

    if require_complete:
        missing = set(declared_fields) - seen_source
        if missing:
            raise StructPatternSemanticError("SP-105 required field missing")

    return SemanticStructPattern(struct_symbol, tuple(resolved_fields))


def _resolve_struct_pattern_for_type(
    pattern: StructPatternNode,
    expected_type: TypeNode,
    symbols: Mapping[str, Any],
    namespace: ModuleNamespace | None,
    *,
    require_complete: bool,
) -> SemanticStructPattern:
    if not isinstance(expected_type, NamedTypeNode):
        raise StructPatternSemanticError("SP-104 field type mismatch")
    semantic = resolve_struct_pattern(
        pattern,
        symbols,
        namespace,
        require_complete=require_complete,
    )
    if semantic.struct_symbol != expected_type.name:
        raise StructPatternSemanticError("SP-104 field type mismatch")
    return semantic


def semantic_pattern_to_json(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        result = {
            field.name: semantic_pattern_to_json(getattr(value, field.name))
            for field in fields(value)
            if not (field.name == "source_span" and getattr(value, field.name) is None)
        }
        result["node_type"] = type(value).__name__
        return result
    if isinstance(value, Mapping):
        return {str(key): semantic_pattern_to_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [semantic_pattern_to_json(item) for item in value]
    return value


def semantic_pattern_from_json(value: Mapping[str, Any]) -> SemanticStructPattern:
    node = _semantic_node(value)
    if not isinstance(node, SemanticStructPattern):
        raise ValueError("document must contain SemanticStructPattern")
    return node


def _semantic_node(value: Mapping[str, Any]) -> Any:
    node_type = value.get("node_type")
    if node_type == "SemanticStructPattern":
        return SemanticStructPattern(
            value["struct_symbol"],
            tuple(_semantic_node(item) for item in value["fields"]),
            value.get("source_span"),
        )
    if node_type == "SemanticOrPattern":
        return SemanticOrPattern(tuple(_semantic_node(item) for item in value["alternatives"]))
    if node_type == "SemanticStructFieldPattern":
        return SemanticStructFieldPattern(
            value["field_symbol"],
            value["field_type"],
            _semantic_node(value["pattern"]),
        )
    if node_type == "SemanticQualifiedPattern":
        return SemanticQualifiedPattern(value["namespace"], value["identifier"])
    if node_type == "SemanticLiteralPattern":
        return SemanticLiteralPattern(value["value"], value["literal_type"])
    if node_type == "SemanticWildcardPattern":
        return SemanticWildcardPattern()
    if node_type == "SemanticDefaultPattern":
        return SemanticDefaultPattern()
    if node_type == "SemanticBindingPattern":
        return SemanticBindingPattern(value["field_symbol"], value["binding"])
    raise ValueError(f"unknown semantic pattern node_type: {node_type}")


def _resolve_struct(
    type_name: str,
    symbols: Mapping[str, Any],
    namespace: ModuleNamespace | None,
) -> tuple[str, StructDeclarationNode]:
    if "." not in type_name:
        declaration = symbols.get(type_name)
        if isinstance(declaration, StructDeclarationNode):
            return type_name, declaration
        if namespace is not None:
            try:
                imported = namespace.imported(type_name)
            except NamespaceResolutionError as error:
                raise StructPatternSemanticError("SP-101 undefined struct") from error
            if imported is not None and isinstance(imported.node, StructDeclarationNode):
                return imported.name, imported.node
        raise StructPatternSemanticError("SP-101 undefined struct")

    module_name, symbol_name = type_name.rsplit(".", 1)
    if namespace is None:
        raise StructPatternSemanticError("SP-101 undefined struct")
    candidates = [
        module
        for name, module in namespace._namespaces.items()
        if name == module_name or name.endswith(f".{module_name}")
    ]
    if len(candidates) != 1:
        raise StructPatternSemanticError("SP-101 undefined struct")
    symbol = candidates[0].symbols.get(symbol_name)
    if symbol is None or not isinstance(symbol.node, StructDeclarationNode):
        raise StructPatternSemanticError("SP-101 undefined struct")
    if candidates[0] is not namespace and not symbol.public:
        raise StructPatternSemanticError("SP-101 undefined struct")
    return symbol.name, symbol.node


def _resolve_terminal_pattern(
    pattern: Pattern,
    field_type: TypeNode,
    symbols: Mapping[str, Any],
    namespace: ModuleNamespace | None,
) -> SemanticPattern:
    if isinstance(pattern, QualifiedPatternNode):
        enum = _resolve_enum(pattern.namespace, symbols, namespace)
        if pattern.identifier not in {value.name for value in enum.values}:
            raise StructPatternSemanticError("SP-104 field type mismatch")
        if not (
            isinstance(field_type, NamedTypeNode)
            and field_type.name == enum.name
        ):
            raise StructPatternSemanticError("SP-104 field type mismatch")
        return SemanticQualifiedPattern(enum.name, pattern.identifier)
    if isinstance(pattern, LiteralPatternNode):
        literal_type = _literal_type(pattern.value)
        if not _type_matches(field_type, literal_type):
            raise StructPatternSemanticError("SP-104 field type mismatch")
        return SemanticLiteralPattern(_literal_value(pattern.value), _type_symbol(literal_type))
    if isinstance(pattern, StructBindingPatternNode):
        return SemanticBindingPattern(pattern.field, pattern.binding)
    if isinstance(pattern, IdentifierPatternNode):
        return SemanticBindingPattern(pattern.name, pattern.name)
    if isinstance(pattern, WildcardPatternNode):
        return SemanticWildcardPattern()
    if isinstance(pattern, DefaultPatternNode):
        return SemanticDefaultPattern()
    if isinstance(pattern, OrPatternNode):
        return SemanticOrPattern(
            tuple(
                resolve_pattern(
                    alternative,
                    field_type,
                    symbols,
                    namespace,
                )
                for alternative in pattern.alternatives
            )
        )
    raise StructPatternSemanticError("SP-104 field type mismatch")


def _resolve_enum(
    enum_name: str,
    symbols: Mapping[str, Any],
    namespace: ModuleNamespace | None,
) -> EnumDeclarationNode:
    declaration = symbols.get(enum_name)
    if isinstance(declaration, EnumDeclarationNode):
        return declaration
    if namespace is not None:
        try:
            imported = namespace.imported(enum_name)
        except NamespaceResolutionError as error:
            raise StructPatternSemanticError("SP-104 field type mismatch") from error
        if imported is not None and isinstance(imported.node, EnumDeclarationNode):
            return imported.node
    raise StructPatternSemanticError("SP-104 field type mismatch")


def _literal_type(value: Any) -> TypeNode:
    if isinstance(value, IntegerLiteralNode):
        return PrimitiveTypeNode(PrimitiveKind.INT)
    if isinstance(value, FloatLiteralNode):
        return PrimitiveTypeNode(PrimitiveKind.FLOAT)
    if isinstance(value, BooleanLiteralNode):
        return PrimitiveTypeNode(PrimitiveKind.BOOL)
    if isinstance(value, StringLiteralNode):
        return PrimitiveTypeNode(PrimitiveKind.STRING)
    if isinstance(value, NullLiteralNode):
        return PrimitiveTypeNode(PrimitiveKind.NULL)
    raise StructPatternSemanticError("SP-104 field type mismatch")


def _literal_value(value: Any) -> Any:
    return getattr(value, "value", None)


def _type_matches(expected: TypeNode, actual: TypeNode) -> bool:
    return expected == actual


def _type_symbol(value: TypeNode) -> str:
    if isinstance(value, NamedTypeNode):
        return value.name
    if isinstance(value, PrimitiveTypeNode):
        return value.kind.value
    return type(value).__name__


def _binding_names(pattern: SemanticPattern) -> tuple[str, ...]:
    if isinstance(pattern, SemanticBindingPattern):
        return (pattern.binding,)
    if isinstance(pattern, SemanticStructPattern):
        names: list[str] = []
        for field in pattern.fields:
            names.extend(_binding_names(field.pattern))
        return tuple(names)
    if isinstance(pattern, SemanticOrPattern) and pattern.alternatives:
        return _binding_names(pattern.alternatives[0])
    return ()
