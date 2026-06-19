"""world.validation - validate World Model SDK Phase 1 consistency."""

from __future__ import annotations

from typing import Any

from .builder import Event, Scene, Transform, World
from .spatial import validate_geometry, validate_hierarchy, validate_spatial_relations

_EVENT_TYPES = {"create", "destroy", "move", "modify", "interact"}
_SCHEMAS = {"world-model-sdk/0.1", "world-model-sdk/0.2", "world-model-sdk/0.3"}


def validate(world: World | dict[str, Any]) -> bool:
    data = world.to_dict() if isinstance(world, World) else world
    if data.get("schema") not in _SCHEMAS:
        return False
    if not data.get("id"):
        return False
    scenes = data.get("scenes")
    if not isinstance(scenes, list):
        return False
    scene_ids = [scene.get("id") for scene in scenes]
    if len(scene_ids) != len(set(scene_ids)):
        return False
    if not all(_validate_scene(scene) for scene in scenes):
        return False
    item_ids = _world_item_ids(scenes)
    events = data.get("events", [])
    if not isinstance(events, list):
        return False
    return _validate_events(events, item_ids)


def validate_scene(scene: Scene | dict[str, Any]) -> bool:
    if isinstance(scene, Scene):
        if not validate_hierarchy(scene) or not validate_spatial_relations(scene):
            return False
    data = scene.to_dict() if isinstance(scene, Scene) else scene
    return _validate_scene(data)


def validate_transform(transform: Transform | dict[str, Any]) -> bool:
    data = transform.to_dict() if isinstance(transform, Transform) else transform
    return all(_is_vector3(data.get(key)) for key in ("position", "rotation", "scale"))


def validate_event(event: Event | dict[str, Any], item_ids: set[str] | None = None) -> bool:
    data = event.to_dict() if isinstance(event, Event) else event
    return _validate_event(data, item_ids or set())


def _validate_scene(scene: dict[str, Any]) -> bool:
    if not scene.get("id"):
        return False
    entities = scene.get("entities", [])
    objects = scene.get("objects", [])
    relations = scene.get("relations", [])
    events = scene.get("events", [])
    if not all(isinstance(items, list) for items in (entities, objects, relations, events)):
        return False

    entity_ids = [entity.get("id") for entity in entities]
    object_ids = [obj.get("id") for obj in objects]
    world_item_ids = entity_ids + object_ids
    if len(world_item_ids) != len(set(world_item_ids)):
        return False
    if any(not item_id for item_id in world_item_ids):
        return False
    for entity in entities:
        if not validate_transform(entity.get("transform", {})):
            return False
        geometry = entity.get("geometry")
        if geometry is not None and not validate_geometry(geometry):
            return False
    for obj in objects:
        if not validate_transform(obj.get("transform", {})):
            return False
        geometry = obj.get("geometry")
        if geometry is not None and not validate_geometry(geometry):
            return False

    relation_ids = [relation.get("id") for relation in relations]
    if len(relation_ids) != len(set(relation_ids)):
        return False
    item_id_set = set(world_item_ids)
    for relation in relations:
        if not relation.get("id") or not relation.get("relation_type"):
            return False
        if relation.get("source") not in item_id_set or relation.get("target") not in item_id_set:
            return False

    event_ids = [event.get("id") for event in events]
    if len(event_ids) != len(set(event_ids)):
        return False
    return _validate_events(events, item_id_set)


def _validate_events(events: list[dict[str, Any]], item_ids: set[str]) -> bool:
    event_ids = [event.get("id") for event in events]
    if len(event_ids) != len(set(event_ids)):
        return False
    return all(_validate_event(event, item_ids) for event in events)


def _validate_event(event: dict[str, Any], item_ids: set[str]) -> bool:
    if not event.get("id") or event.get("event_type") not in _EVENT_TYPES:
        return False
    target = event.get("target")
    if target is not None and target not in item_ids:
        return False
    if event.get("event_type") == "create":
        payload = event.get("payload", {})
        if not isinstance(payload, dict) or not payload.get("id"):
            return False
        if payload.get("world_item_type", "object") not in {"entity", "object"}:
            return False
    return True


def _world_item_ids(scenes: list[dict[str, Any]]) -> set[str]:
    item_ids: set[str] = set()
    for scene in scenes:
        item_ids.update(entity.get("id") for entity in scene.get("entities", []))
        item_ids.update(obj.get("id") for obj in scene.get("objects", []))
    return {item_id for item_id in item_ids if item_id}


def _is_vector3(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(component, (int, float)) for component in value)
    )
