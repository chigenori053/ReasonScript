"""Core language module and namespace validation."""

from .module_system import (
    ImportCycleError,
    ModuleResolutionError,
    ResolvedModule,
    Symbol,
    SymbolKind,
    UnknownModuleError,
    UnknownSymbolError,
    resolve_modules,
)

__all__ = [
    "ImportCycleError",
    "ModuleResolutionError",
    "ResolvedModule",
    "Symbol",
    "SymbolKind",
    "UnknownModuleError",
    "UnknownSymbolError",
    "resolve_modules",
]
