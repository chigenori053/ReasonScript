"""world.metadata - World Model SDK metadata helpers."""

from __future__ import annotations

from typing import Any


def build_world_model_metadata(version: str = "0.3") -> dict[str, Any]:
    return {"world_model": {"version": version}}


def inject_world_model_metadata(metadata: dict[str, Any], version: str = "0.3") -> dict[str, Any]:
    result = dict(metadata)
    result["world_model"] = {"version": version}
    return result
