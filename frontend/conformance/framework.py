from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
VALID_FIXTURES = FRONTEND / "fixtures" / "valid"
INVALID_FIXTURES = FRONTEND / "fixtures" / "invalid"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_ast(value: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    result.setdefault("imports", [])
    result.setdefault("metadata", [])
    for node in result["declarations"]:
        if node["node_type"] == "TransitionNode":
            node.setdefault("expected_cost", 1.0)
            if node.get("guard") is None:
                node.pop("guard", None)
            if node.get("effect") is None:
                node.pop("effect", None)
    return result


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        canonical_ast(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
