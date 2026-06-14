"""Closed-program namespace and import resolution for Language Surface LS-2."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass, replace
from typing import Any, Mapping

from .nodes import (
    CalculationNode,
    ImportNode,
    ImportResolutionNode,
    ModuleNode,
    ProgramNode,
    QualifiedIdentifierNode,
    Visibility,
)


class NamespaceResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class SurfaceSymbol:
    module: str
    name: str
    node: Any
    public: bool

    @property
    def qualified_name(self) -> str:
        return f"{self.module}::{self.name}"


@dataclass(frozen=True)
class ImportBinding:
    node: ImportNode
    namespace: str
    symbol: SurfaceSymbol | None
    exposed: dict[str, SurfaceSymbol]
    qualifier: str | None
    expose_unqualified: bool = True
    external: bool = False


@dataclass(frozen=True)
class ModuleNamespace:
    module: ModuleNode
    symbols: dict[str, SurfaceSymbol]
    imports: tuple[ImportBinding, ...]
    _namespaces: Mapping[str, "ModuleNamespace"] = field(
        default_factory=dict, repr=False, compare=False
    )

    def imported(self, name: str) -> SurfaceSymbol | None:
        candidates = {
            binding.exposed[name].qualified_name: binding.exposed[name]
            for binding in self.imports
            if binding.expose_unqualified and name in binding.exposed
        }
        if len(candidates) > 1:
            raise NamespaceResolutionError(f"NS-040 NS-V007 ambiguous symbol: {name}")
        return next(iter(candidates.values()), None)

    def resolve_qualified(
        self, reference: QualifiedIdentifierNode
    ) -> SurfaceSymbol:
        qualifier = "::".join(reference.path)
        for binding in self.imports:
            if binding.qualifier == qualifier:
                if binding.symbol is not None:
                    if reference.symbol != binding.symbol.name:
                        break
                    return binding.symbol
                symbol = binding.exposed.get(reference.symbol)
                if symbol is not None:
                    return symbol
                target_namespace = self._namespaces.get(binding.namespace)
                private = (
                    target_namespace.symbols.get(reference.symbol)
                    if target_namespace is not None
                    else None
                )
                if private is not None and not private.public:
                    raise NamespaceResolutionError(
                        f"NS-050 NS-V006 private symbol is not importable: "
                        f"{private.qualified_name}"
                    )
                break

        modules = _module_candidates(reference.path)
        for module_name in modules:
            namespace = self._namespaces.get(module_name)
            if namespace is None:
                continue
            symbol = namespace.symbols.get(reference.symbol)
            if symbol is None:
                break
            if module_name != self.module.name and not symbol.public:
                raise NamespaceResolutionError(
                    f"NS-050 NS-V006 private symbol is not importable: "
                    f"{symbol.qualified_name}"
                )
            return symbol
        raise NamespaceResolutionError(
            f"NS-030 NS-V005 qualified target does not exist: "
            f"{qualifier}::{reference.symbol}"
        )


def resolve_program(
    program: ProgramNode, *, strict: bool = True
) -> tuple[ProgramNode, dict[str, ModuleNamespace]]:
    modules = {module.name: module for module in program.modules}
    symbols = {name: _symbols(module) for name, module in modules.items()}
    provisional = {
        name: ModuleNamespace(module, symbols[name], ())
        for name, module in modules.items()
    }
    for namespace in provisional.values():
        object.__setattr__(namespace, "_namespaces", provisional)
    resolved: dict[str, ModuleNamespace] = {}
    enriched_modules: list[ModuleNode] = []

    for module in program.modules:
        bindings = _imports(module, modules, symbols, strict=strict)
        _reject_ambiguous_imports(bindings)
        namespace = ModuleNamespace(module, symbols[module.name], tuple(bindings))
        resolved[module.name] = namespace
        enriched_body = tuple(
            _enrich_import(node, bindings) if isinstance(node, ImportNode) else node
            for node in module.body
        )
        enriched_modules.append(replace(module, body=enriched_body))

    for namespace in resolved.values():
        object.__setattr__(namespace, "_namespaces", resolved)
    enriched = ProgramNode(tuple(enriched_modules))
    canonical_modules = tuple(
        _enrich_value(module, resolved[module.name])
        for module in enriched.modules
    )
    return ProgramNode(canonical_modules), resolved


def _symbols(module: ModuleNode) -> dict[str, SurfaceSymbol]:
    result: dict[str, SurfaceSymbol] = {}
    for node in module.body:
        if not hasattr(node, "name"):
            continue
        name = node.name
        if name in result:
            raise NamespaceResolutionError(
                f"NS-001 NS-V002 duplicate symbol in {module.name}: {name}"
            )
        public = (
            node.visibility == Visibility.PUBLIC
            if isinstance(node, CalculationNode)
            else module.visibility == Visibility.PUBLIC
        )
        result[name] = SurfaceSymbol(module.name, name, node, public)
    return result


def _imports(
    module: ModuleNode,
    modules: dict[str, ModuleNode],
    symbols: dict[str, dict[str, SurfaceSymbol]],
    *,
    strict: bool,
) -> list[ImportBinding]:
    bindings: list[ImportBinding] = []
    aliases: set[str] = set()
    local_names = set(symbols[module.name])
    for node in (item for item in module.body if isinstance(item, ImportNode)):
        target = ".".join(node.path)
        namespace_name, symbol_name = _import_target(node.path, modules, symbols)
        if namespace_name is None:
            known_prefix = any(
                ".".join(node.path[:end]) in modules
                for end in range(1, len(node.path) + 1)
            )
            if strict and known_prefix:
                raise NamespaceResolutionError(
                    f"NS-020 NS-V003 import target does not exist: {target}"
                )
            if strict and len(node.path) == 1:
                raise NamespaceResolutionError(
                    f"NS-020 NS-V003 import target does not exist: {target}"
                )
            qualifier = node.alias or node.path[-1]
            _register_alias(qualifier, aliases, local_names)
            bindings.append(
                ImportBinding(
                    node,
                    target,
                    None,
                    {},
                    qualifier,
                    expose_unqualified=False,
                    external=True,
                )
            )
            continue

        qualifier = node.alias
        if symbol_name is None:
            exposed = {
                name: symbol
                for name, symbol in symbols[namespace_name].items()
                if symbol.public
            }
            private = {
                name for name, symbol in symbols[namespace_name].items() if not symbol.public
            }
            if not exposed and private:
                raise NamespaceResolutionError(
                    f"NS-050 NS-V006 module exports no public symbols: {namespace_name}"
                )
            qualifier = qualifier or namespace_name.split(".")[-1]
            _register_alias(qualifier, aliases, local_names)
            if node.alias is not None:
                expose_unqualified = False
            else:
                expose_unqualified = True
        else:
            symbol = symbols[namespace_name][symbol_name]
            if not symbol.public:
                raise NamespaceResolutionError(
                    f"NS-050 NS-V006 private symbol is not importable: "
                    f"{symbol.qualified_name}"
                )
            exposed_name = node.alias or symbol_name
            _register_alias(exposed_name, aliases, local_names)
            exposed = {exposed_name: symbol}
            qualifier = node.alias
            bindings.append(
                ImportBinding(node, namespace_name, symbol, exposed, qualifier)
            )
            continue
        bindings.append(
            ImportBinding(
                node,
                namespace_name,
                None,
                exposed,
                qualifier,
                expose_unqualified=expose_unqualified,
            )
        )
    return bindings


def _import_target(
    path: tuple[str, ...],
    modules: dict[str, ModuleNode],
    symbols: dict[str, dict[str, SurfaceSymbol]],
) -> tuple[str | None, str | None]:
    full = ".".join(path)
    if full in modules:
        return full, None
    for end in range(len(path) - 1, 0, -1):
        module_name = ".".join(path[:end])
        symbol_name = ".".join(path[end:])
        if module_name in modules and symbol_name in symbols[module_name]:
            return module_name, symbol_name
    return None, None


def _register_alias(alias: str, aliases: set[str], local_names: set[str]) -> None:
    if alias in aliases or alias in local_names:
        raise NamespaceResolutionError(
            f"NS-021 NS-V004 alias conflicts with existing name: {alias}"
        )
    aliases.add(alias)


def _reject_ambiguous_imports(bindings: list[ImportBinding]) -> None:
    imported: dict[str, set[str]] = {}
    for binding in bindings:
        if not binding.expose_unqualified:
            continue
        for name, symbol in binding.exposed.items():
            imported.setdefault(name, set()).add(symbol.qualified_name)
    ambiguous = sorted(name for name, targets in imported.items() if len(targets) > 1)
    if ambiguous:
        raise NamespaceResolutionError(
            f"NS-040 NS-V007 ambiguous imported symbol: {ambiguous[0]}"
        )


def _enrich_import(node: ImportNode, bindings: list[ImportBinding]) -> ImportNode:
    binding = next(item for item in bindings if item.node is node)
    resolution = ImportResolutionNode(
        namespace=binding.namespace,
        symbol=binding.symbol.name if binding.symbol is not None else None,
        exposed_names=tuple(sorted(binding.exposed)),
    )
    return replace(node, resolution=resolution)


def _module_candidates(path: tuple[str, ...]) -> tuple[str, ...]:
    dotted = ".".join(path)
    return tuple(
        sorted(
            {
                dotted,
                "::".join(path),
                path[0],
            },
            key=len,
            reverse=True,
        )
    )


def _enrich_value(value: Any, namespace: ModuleNamespace) -> Any:
    if isinstance(value, QualifiedIdentifierNode):
        symbol = namespace.resolve_qualified(value)
        return replace(value, resolved_name=symbol.qualified_name)
    if is_dataclass(value) and not isinstance(value, type):
        changes = {
            field.name: _enrich_value(getattr(value, field.name), namespace)
            for field in fields(value)
        }
        return replace(value, **changes)
    if isinstance(value, tuple):
        return tuple(_enrich_value(item, namespace) for item in value)
    if isinstance(value, list):
        return [_enrich_value(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            key: _enrich_value(item, namespace)
            for key, item in value.items()
        }
    return value
