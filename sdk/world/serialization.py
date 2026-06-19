"""world.serialization - deterministic JSON serialization."""

from __future__ import annotations

import json
from typing import Any

from .builder import World


def to_json(world: World | dict[str, Any]) -> str:
    data = world.to_dict() if isinstance(world, World) else world
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def to_dict(world: World) -> dict[str, Any]:
    return world.to_dict()
