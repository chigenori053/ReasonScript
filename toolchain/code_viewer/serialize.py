"""ViewerDocument → plain JSON, for `reason view --json`.

Mirrors the to_json_value() convention already used by
frontend.language_surface.nodes and frontend.ast: a small generic
dataclass/Enum/Mapping/sequence walker, not a bespoke serializer per type.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Mapping


def to_json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {
            (key.value if isinstance(key, Enum) else str(key)): to_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [to_json_value(item) for item in value]
    return value
