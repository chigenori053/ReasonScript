"""world.query - inspect World SDK models without mutation."""

from __future__ import annotations

from .builder import Scene, World


def scene_ids(world: World) -> list[str]:
    return [scene.id for scene in world.scenes]


def entity_ids(scene: Scene) -> list[str]:
    return [entity.id for entity in scene.entities]


def object_ids(scene: Scene) -> list[str]:
    return [obj.id for obj in scene.objects]


def relation_ids(scene: Scene) -> list[str]:
    return [relation.id for relation in scene.relations]


def event_ids(scene: Scene) -> list[str]:
    return [event.id for event in scene.events]


def snapshot_ids(world: World) -> list[str]:
    return [snapshot.id for snapshot in world.snapshots]
