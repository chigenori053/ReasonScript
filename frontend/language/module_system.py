"""Deterministic module, namespace, and import resolution for Language v0.1."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from frontend.ast import (
    ConstraintNode,
    ContextNode,
    GoalNode,
    ModuleNode,
    StateNode,
    TransitionNode,
    validate,
)

_MODULE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")


class ModuleResolutionError(ValueError):
    """Base error for deterministic module resolution failures."""


class UnknownModuleError(ModuleResolutionError):
    pass


class ImportCycleError(ModuleResolutionError):
    pass


class UnknownSymbolError(ModuleResolutionError):
    pass


class SymbolKind(str, Enum):
    GOAL = "goal"
    STATE = "state"
    TRANSITION = "transition"
    CONSTRAINT = "constraint"
    CONTEXT = "context"


@dataclass(frozen=True)
class Symbol:
    module: str
    name: str
    kind: SymbolKind
    node_id: str

    @property
    def qualified_name(self) -> str:
        return f"{self.module}.{self.name}"


@dataclass(frozen=True)
class ResolvedModule:
    name: str
    imports: tuple[str, ...]
    symbols: Mapping[str, Symbol]
    _dependencies: Mapping[str, "ResolvedModule"] = field(
        default_factory=dict, repr=False, compare=False
    )

    def resolve(self, reference: str) -> Symbol:
        local = self.symbols.get(reference)
        if local is not None:
            return local

        candidates = sorted((self.name, *self.imports), key=len, reverse=True)
        for module_name in candidates:
            prefix = f"{module_name}."
            if reference.startswith(prefix):
                symbol_name = reference[len(prefix) :]
                target = self if module_name == self.name else self._dependencies[module_name]
                symbol = target.symbols.get(symbol_name)
                if symbol is not None:
                    return symbol
                raise UnknownSymbolError(f"unknown symbol in {module_name}: {symbol_name}")
        raise UnknownSymbolError(f"unknown symbol in {self.name}: {reference}")

def resolve_modules(modules: Mapping[str, ModuleNode]) -> Mapping[str, ResolvedModule]:
    """Validate a closed module graph and return immutable resolved namespaces."""
    if not modules:
        return MappingProxyType({})

    for name, module in modules.items():
        _validate_module_name(name)
        validate(module)
        for imported in module.imports:
            _validate_module_name(imported)
            if imported not in modules:
                raise UnknownModuleError(f"{name} imports unknown module {imported}")

    _reject_cycles(modules)
    resolved = {
        name: ResolvedModule(
            name=name,
            imports=module.imports,
            symbols=MappingProxyType(_symbols(name, module)),
        )
        for name, module in modules.items()
    }
    for module in resolved.values():
        object.__setattr__(
            module,
            "_dependencies",
            MappingProxyType({name: resolved[name] for name in module.imports}),
        )
    return MappingProxyType(resolved)


def _symbols(module_name: str, module: ModuleNode) -> dict[str, Symbol]:
    result: dict[str, Symbol] = {}
    for node in module.declarations:
        if isinstance(node, GoalNode):
            name, kind = "goal", SymbolKind.GOAL
        elif isinstance(node, StateNode):
            name, kind = node.state_id, SymbolKind.STATE
        elif isinstance(node, TransitionNode):
            name, kind = node.transition_id, SymbolKind.TRANSITION
        elif isinstance(node, ConstraintNode):
            name, kind = node.constraint_id, SymbolKind.CONSTRAINT
        elif isinstance(node, ContextNode):
            name, kind = node.context_id, SymbolKind.CONTEXT
        else:
            continue
        if name in result:
            raise ModuleResolutionError(
                f"duplicate exported symbol in {module_name}: {name}"
            )
        result[name] = Symbol(module_name, name, kind, node.node_id)
    return result


def _validate_module_name(name: str) -> None:
    if not isinstance(name, str) or not _MODULE_NAME.fullmatch(name):
        raise ModuleResolutionError(f"invalid canonical module name: {name!r}")


def _reject_cycles(modules: Mapping[str, ModuleNode]) -> None:
    visited: set[str] = set()
    active: list[str] = []

    def visit(name: str) -> None:
        if name in active:
            start = active.index(name)
            cycle = active[start:] + [name]
            raise ImportCycleError("cyclic import: " + " -> ".join(cycle))
        if name in visited:
            return
        active.append(name)
        for imported in modules[name].imports:
            visit(imported)
        active.pop()
        visited.add(name)

    for name in modules:
        visit(name)
