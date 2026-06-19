"""world.runtime - Runtime SDK compatibility helpers."""

from __future__ import annotations

from frontend.runtime_integration import RuntimeValue

from .builder import World


def runtime_value(world: World) -> RuntimeValue:
    return RuntimeValue("WorldModelValue", world.to_dict())
