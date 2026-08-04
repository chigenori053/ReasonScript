"""Generic flattening of a compiled-stage JSON value into StageNode rows.

Surface AST and Semantic AST are converted to plain JSON via each package's
own `to_json_value` (frontend.language_surface.nodes / frontend.ast) before
reaching this module; Reason IR and ExecutionPlan are already plain dict/list
JSON. That normalization means one tree-walker here covers all four stages —
CodeViewer does not need per-node-type rendering rules for the 100+ AST node
classes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .model import StageNode

AnchorResolver = Callable[[Mapping[str, Any]], "str | None"]


def flatten(value: Any, *, resolve_anchor: AnchorResolver) -> tuple[StageNode, ...]:
    nodes: list[StageNode] = []
    _walk(nodes, value, depth=0, label="", json_pointer="", resolve_anchor=resolve_anchor)
    return tuple(nodes)


def _walk(
    nodes: list[StageNode],
    value: Any,
    *,
    depth: int,
    label: str,
    json_pointer: str,
    resolve_anchor: AnchorResolver,
) -> None:
    pointer = json_pointer or "/"

    if isinstance(value, Mapping):
        anchor = resolve_anchor(value)
        node_type = value.get("node_type")
        text = f"{label}: {node_type}" if label and node_type else (node_type or label or "{}")
        nodes.append(StageNode(node_id=pointer, depth=depth, label=text, anchor=anchor, json_pointer=pointer))
        for key, item in value.items():
            if key == "node_type":
                continue
            _walk(
                nodes,
                item,
                depth=depth + 1,
                label=str(key),
                json_pointer=f"{json_pointer}/{key}",
                resolve_anchor=resolve_anchor,
            )
        return

    if isinstance(value, (list, tuple)):
        text = f"{label} [{len(value)}]" if label else f"[{len(value)}]"
        nodes.append(StageNode(node_id=pointer, depth=depth, label=text, anchor=None, json_pointer=pointer))
        for index, item in enumerate(value):
            _walk(
                nodes,
                item,
                depth=depth + 1,
                label=f"[{index}]",
                json_pointer=f"{json_pointer}/{index}",
                resolve_anchor=resolve_anchor,
            )
        return

    text = f"{label}: {_scalar_repr(value)}" if label else _scalar_repr(value)
    nodes.append(StageNode(node_id=pointer, depth=depth, label=text, anchor=None, json_pointer=pointer))


def _scalar_repr(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)
