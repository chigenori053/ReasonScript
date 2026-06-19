"""world.validation - validate World SDK Phase 1 consistency."""

from __future__ import annotations

from typing import Any

from .builder import Scene, Transform, World


def validate(world: World | dict[str, Any]) -> bool:
    data = world.to_dict() if isinstance(world, World) else world
    if data.get("schema_version") != "world-sdk/0.1":
        return False
    if not data.get("name"):
        return False
    scenes = data.get("scenes")
    if not isinstance(scenes, list):
        return False
    scene_ids = [scene.get("id") for scene in scenes]
    if len(scene_ids) != len(set(scene_ids)):
        return False
    return all(_validate_scene(scene) for scene in scenes)


def validate_scene(scene: Scene | dict[str, Any]) -> bool:
    data = scene.to_dict() if isinstance(scene, Scene) else scene
    return _validate_scene(data)


def validate_transform(transform: Transform | dict[str, Any]) -> bool:
    data = transform.to_dict() if isinstance(transform, Transform) else transform
    return all(_is_vector3(data.get(key)) for key in ("position", "rotation", "scale"))


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
    for obj in objects:
        if not validate_transform(obj.get("transform", {})):
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
    for event in events:
        if not event.get("id") or not event.get("event_type"):
            return False
        target = event.get("target")
        if target is not None and target not in item_id_set:
            return False
    return True


def _is_vector3(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(component, (int, float)) for component in value)
    )
