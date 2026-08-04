"""Dependency-free public contracts for the ReasonScript Vision namespace."""

from __future__ import annotations

from typing import Any


PROFILE = "reasonscript-vision-language-integration/0.1"
VISION_TYPES = ("VisionModel", "VisionObservation", "VisionBuildResult")
_FUNCTIONS = (
    {
        "qualified_name": "vision.infer",
        "input_type": "Path,Path",
        "output_type": "VisionObservation",
        "native_operation": "vision_infer",
        "capabilities": ["filesystem_read"],
    },
    {
        "qualified_name": "vision.build_ruo",
        "input_type": "VisionObservation,Path",
        "output_type": "VisionBuildResult",
        "native_operation": "vision_build_ruo",
        "capabilities": ["filesystem_write"],
    },
)


def public_registry() -> tuple[dict[str, Any], ...]:
    return tuple({"version": "0.1", "determinism": "verified-input", **entry} for entry in _FUNCTIONS)
