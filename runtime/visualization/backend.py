"""Exchangeable visualization backend contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from runtime.data import Table

from .model import VisualizationSpec


class VisualizationBackend(ABC):
    id = "abstract"
    @abstractmethod
    def available(self) -> bool: ...
    @abstractmethod
    def render(self, spec: VisualizationSpec, table: Table, output_dir: str | Path) -> dict[str, Any]: ...

    def capabilities(self) -> dict[str, Any]:
        return {"id": self.id, "formats": ["png", "svg"], "available": self.available()}
