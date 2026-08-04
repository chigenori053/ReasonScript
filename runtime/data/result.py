"""Typed separation between public analysis results and runtime context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .backend import DataBackend
from .model import Table


@dataclass(frozen=True)
class TitanicAnalysisResult:
    value: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.value.copy()


@dataclass(frozen=True)
class TitanicAnalysisExecution:
    result: TitanicAnalysisResult
    table: Table
    backend: DataBackend
