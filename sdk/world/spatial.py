"""world.spatial - World Model SDK Phase 2 spatial layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .builder import Relation, Scene, Transform, WorldEntity, WorldObject

GEOMETRY_TYPES = {
    "Point2D",
    "Rectangle2D",
    "Circle2D",
    "Triangle2D",
    "Point3D",
    "Cube3D",
    "Sphere3D",
    "Cylinder3D",
}
SPATIAL_RELATIONS = {
    "left_of",
    "right_of",
    "above",
    "below",
    "inside",
    "contains",
    "near",
    "far",
}
LAYOUT_RELATIONS = {"left_of", "right_of", "above", "below", "inside", "contains"}


@dataclass(frozen=True)
class Geometry:
    id: str
    geometry_type: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.geometry_type,
            "parameters": dict(self.parameters),
        }


def create_geometry(geometry_id: str, geometry_type: str, **parameters: Any) -> Geometry:
    return Geometry(id=geometry_id, geometry_type=geometry_type, parameters=dict(parameters))


def validate_geometry(geometry: Geometry | dict[str, Any]) -> bool:
    data = geometry.to_dict() if isinstance(geometry, Geometry) else geometry
    geometry_type = data.get("type")
    parameters = data.get("parameters", {})
    if not data.get("id") or geometry_type not in GEOMETRY_TYPES or not isinstance(parameters, dict):
        return False
    required = {
        "Point2D": ("x", "y"),
        "Rectangle2D": ("width", "height"),
        "Circle2D": ("radius",),
        "Triangle2D": ("points",),
        "Point3D": ("x", "y", "z"),
        "Cube3D": ("width", "height", "depth"),
        "Sphere3D": ("radius",),
        "Cylinder3D": ("radius", "height"),
    }[geometry_type]
    return all(key in parameters for key in required)


def add_spatial_relation(scene: Scene, relation_id: str, source: str, target: str, relation_type: str) -> Scene:
    relation = Relation(id=relation_id, source=source, target=target, relation_type=relation_type)
    if any(existing.id == relation.id for existing in scene.relations):
        return scene
    return Scene(
        id=scene.id,
        entities=scene.entities,
        objects=scene.objects,
        relations=scene.relations + (relation,),
        events=scene.events,
    )


def attach_child(scene: Scene, parent_id: str, child_id: str) -> Scene:
    if parent_id == child_id or parent_id not in _item_ids(scene) or child_id not in _item_ids(scene):
        return scene
    return set_parent(scene, child_id, parent_id)


def set_parent(scene: Scene, child_id: str, parent_id: str | None) -> Scene:
    entities = tuple(_set_item_parent(entity, child_id, parent_id) for entity in scene.entities)
    objects = tuple(_set_item_parent(obj, child_id, parent_id) for obj in scene.objects)
    entities = tuple(_set_parent_children(entity, parent_id, child_id) for entity in entities)
    objects = tuple(_set_parent_children(obj, parent_id, child_id) for obj in objects)
    return Scene(
        id=scene.id,
        entities=entities,
        objects=objects,
        relations=scene.relations,
        events=scene.events,
    )


def validate_hierarchy(scene: Scene) -> bool:
    items = _items(scene)
    item_ids = set(items)
    parent_count: dict[str, int] = {item_id: 0 for item_id in item_ids}
    for item_id, item in items.items():
        parent_id = getattr(item, "parent_id", None)
        if parent_id is not None:
            if parent_id not in item_ids:
                return False
            parent_count[item_id] += 1
    if any(count > 1 for count in parent_count.values()):
        return False
    for item_id in item_ids:
        seen: set[str] = set()
        cursor = item_id
        while True:
            parent_id = getattr(items[cursor], "parent_id", None)
            if parent_id is None:
                break
            if parent_id in seen or parent_id == item_id:
                return False
            seen.add(parent_id)
            cursor = parent_id
    return True


def validate_spatial_relations(scene: Scene) -> bool:
    item_ids = _item_ids(scene)
    for relation in scene.relations:
        if relation.relation_type in SPATIAL_RELATIONS:
            if relation.source not in item_ids or relation.target not in item_ids:
                return False
    return True


def validate_layout(scene: Scene) -> bool:
    return validate_hierarchy(scene) and validate_spatial_relations(scene) and not detect_conflicts(scene)


def detect_conflicts(scene: Scene) -> list[str]:
    conflicts: list[str] = []
    relation_pairs = {
        (relation.source, relation.target, relation.relation_type)
        for relation in scene.relations
        if relation.relation_type in LAYOUT_RELATIONS
    }
    opposites = {
        "left_of": "right_of",
        "right_of": "left_of",
        "above": "below",
        "below": "above",
        "inside": "contains",
        "contains": "inside",
    }
    for source, target, relation_type in sorted(relation_pairs):
        opposite = opposites[relation_type]
        if (source, target, opposite) in relation_pairs:
            conflicts.append(f"direct:{source}:{relation_type}:{opposite}:{target}")
        if (target, source, relation_type) in relation_pairs:
            conflicts.append(f"cyclic:{source}:{relation_type}:{target}")
    return conflicts


def solve_layout(scene: Scene, *, spacing: float = 1.0) -> Scene:
    entities = {entity.id: entity for entity in scene.entities}
    objects = {obj.id: obj for obj in scene.objects}
    transforms = {item_id: _get_transform(item) for item_id, item in {**entities, **objects}.items()}
    for relation in sorted(scene.relations, key=lambda r: (r.relation_type, r.source, r.target)):
        if relation.relation_type not in LAYOUT_RELATIONS:
            continue
        source_t = transforms.get(relation.source)
        target_t = transforms.get(relation.target)
        if source_t is None or target_t is None:
            continue
        transforms[relation.source] = _resolve_relation_transform(
            relation.relation_type,
            source_t,
            target_t,
            spacing,
        )
    return _replace_transforms(scene, transforms)


def apply_constraint_layout(scene: Scene, *, spacing: float = 1.0) -> Scene:
    return solve_layout(scene, spacing=spacing)


def world_transform(scene: Scene, item_id: str) -> Transform | None:
    items = _items(scene)
    item = items.get(item_id)
    if item is None:
        return None
    local = _get_transform(item)
    parent_id = getattr(item, "parent_id", None)
    if parent_id is None:
        return local
    parent_t = world_transform(scene, parent_id)
    if parent_t is None:
        return None
    return _compose(parent_t, local)


def local_transform(scene: Scene, item_id: str) -> Transform | None:
    item = _items(scene).get(item_id)
    return None if item is None else _get_transform(item)


def children(scene: Scene, item_id: str) -> list[str]:
    return sorted(
        child_id
        for child_id, item in _items(scene).items()
        if getattr(item, "parent_id", None) == item_id
    )


def parent(scene: Scene, item_id: str) -> str | None:
    item = _items(scene).get(item_id)
    return None if item is None else getattr(item, "parent_id", None)


def geometry(scene: Scene, item_id: str) -> Geometry | None:
    item = _items(scene).get(item_id)
    return None if item is None else getattr(item, "geometry", None)


def spatial_relations(scene: Scene) -> list[Relation]:
    return [relation for relation in scene.relations if relation.relation_type in SPATIAL_RELATIONS]


def _resolve_relation_transform(
    relation_type: str,
    source: Transform,
    target: Transform,
    spacing: float,
) -> Transform:
    x, y, z = target.position
    if relation_type == "left_of":
        position = (x - spacing, y, z)
    elif relation_type == "right_of":
        position = (x + spacing, y, z)
    elif relation_type == "above":
        position = (x, y + spacing, z)
    elif relation_type == "below":
        position = (x, y - spacing, z)
    else:
        position = (x, y, z)
    return Transform(position=position, rotation=source.rotation, scale=source.scale)


def _compose(parent_transform: Transform, local: Transform) -> Transform:
    return Transform(
        position=tuple(parent_transform.position[i] + local.position[i] for i in range(3)),
        rotation=tuple(parent_transform.rotation[i] + local.rotation[i] for i in range(3)),
        scale=tuple(parent_transform.scale[i] * local.scale[i] for i in range(3)),
    )


def _replace_transforms(scene: Scene, transforms: dict[str, Transform]) -> Scene:
    return Scene(
        id=scene.id,
        entities=tuple(_replace_item_transform(entity, transforms) for entity in scene.entities),
        objects=tuple(_replace_item_transform(obj, transforms) for obj in scene.objects),
        relations=scene.relations,
        events=scene.events,
    )


def _replace_item_transform(item, transforms: dict[str, Transform]):
    transform = transforms.get(item.id, item.transform)
    if isinstance(item, WorldEntity):
        return WorldEntity(
            id=item.id,
            kind=item.kind,
            state=item.state,
            behavior=item.behavior,
            transform=transform,
            geometry=item.geometry,
            parent_id=item.parent_id,
            children=item.children,
        )
    return WorldObject(
        id=item.id,
        kind=item.kind,
        properties=item.properties,
        transform=transform,
        geometry=item.geometry,
        parent_id=item.parent_id,
        children=item.children,
    )


def _set_item_parent(item, child_id: str, parent_id: str | None):
    if item.id != child_id:
        return item
    if isinstance(item, WorldEntity):
        return WorldEntity(item.id, item.kind, item.state, item.behavior, item.transform, item.geometry, parent_id, item.children)
    return WorldObject(item.id, item.kind, item.properties, item.transform, item.geometry, parent_id, item.children)


def _set_parent_children(item, parent_id: str | None, child_id: str):
    current_children = tuple(c for c in item.children if c != child_id)
    if item.id == parent_id:
        current_children = tuple(sorted(current_children + (child_id,)))
    if isinstance(item, WorldEntity):
        return WorldEntity(item.id, item.kind, item.state, item.behavior, item.transform, item.geometry, item.parent_id, current_children)
    return WorldObject(item.id, item.kind, item.properties, item.transform, item.geometry, item.parent_id, current_children)


def _get_transform(item) -> Transform:
    return item.transform


def _items(scene: Scene) -> dict[str, WorldEntity | WorldObject]:
    return {item.id: item for item in scene.entities + scene.objects}


def _item_ids(scene: Scene) -> set[str]:
    return set(_items(scene))
