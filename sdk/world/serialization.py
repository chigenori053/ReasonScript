"""world.serialization - deterministic JSON serialization."""

from __future__ import annotations

import json
from typing import Any

from .builder import World
from .semantic import ReconstructionResult, templates


def to_json(world: World | dict[str, Any]) -> str:
    data = world.to_dict() if isinstance(world, World) else world
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def to_dict(world: World) -> dict[str, Any]:
    return world.to_dict()


def reconstruction_to_json(result: ReconstructionResult) -> str:
    data = result.to_dict()
    data["schema"] = "world-model-sdk/0.3"
    data["templates"] = [template.to_dict() for template in templates()]
    data["reconstruction"] = result.trace.to_dict()
    data["evidence"] = list(result.trace.evidence)
    return json.dumps(data, sort_keys=True, separators=(",", ":"))
