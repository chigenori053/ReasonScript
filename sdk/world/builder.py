"""world.builder - construct World SDK Phase 1 models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_SCHEMA_VERSION = "world-sdk/0.1"


@dataclass(frozen=True)
class Transform:
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "position": list(self.position),
            "rotation": list(self.rotation),
            "scale": list(self.scale),
        }


@dataclass(frozen=True)
class WorldEntity:
    id: str
    kind: str = "Entity"
    state: dict[str, Any] = field(default_factory=dict)
    behavior: tuple[str, ...] = field(default_factory=tuple)
    transform: Transform = field(default_factory=Transform)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "state": dict(self.state),
            "behavior": list(self.behavior),
            "transform": self.transform.to_dict(),
        }


@dataclass(frozen=True)
class WorldObject:
    id: str
    kind: str = "Object"
    properties: dict[str, Any] = field(default_factory=dict)
    transform: Transform = field(default_factory=Transform)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "properties": dict(self.properties),
            "transform": self.transform.to_dict(),
        }


@dataclass(frozen=True)
class Relation:
    id: str
    source: str
    target: str
    relation_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type,
            "metadata": dict(self.metadata),
            "reason_graph_relation": {
                "from": self.source,
                "to": self.target,
                "relation": self.relation_type,
            },
        }


@dataclass(frozen=True)
class Event:
    id: str
    event_type: str
    target: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    tick: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "target": self.target,
            "payload": dict(self.payload),
            "tick": self.tick,
        }


@dataclass(frozen=True)
class Scene:
    id: str
    entities: tuple[WorldEntity, ...] = field(default_factory=tuple)
    objects: tuple[WorldObject, ...] = field(default_factory=tuple)
    relations: tuple[Relation, ...] = field(default_factory=tuple)
    events: tuple[Event, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entities": [entity.to_dict() for entity in self.entities],
            "objects": [obj.to_dict() for obj in self.objects],
            "relations": [relation.to_dict() for relation in self.relations],
            "events": [event.to_dict() for event in self.events],
        }


@dataclass(frozen=True)
class Snapshot:
    id: str
    world_name: str
    tick: int
    scenes: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "id": self.id,
            "world_name": self.world_name,
            "tick": self.tick,
            "scenes": [dict(scene) for scene in self.scenes],
        }


@dataclass(frozen=True)
class World:
    name: str
    scenes: tuple[Scene, ...] = field(default_factory=tuple)
    snapshots: tuple[Snapshot, ...] = field(default_factory=tuple)
    tick: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "name": self.name,
            "tick": self.tick,
            "scenes": [scene.to_dict() for scene in self.scenes],
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
        }


def create_transform(
    *,
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> Transform:
    return Transform(position=position, rotation=rotation, scale=scale)


def create_world(name: str) -> World:
    return World(name=name)


def create_scene(scene_id: str) -> Scene:
    return Scene(id=scene_id)


def create_entity(
    entity_id: str,
    *,
    kind: str = "Entity",
    state: dict[str, Any] | None = None,
    behavior: tuple[str, ...] = (),
    transform: Transform | None = None,
) -> WorldEntity:
    return WorldEntity(
        id=entity_id,
        kind=kind,
        state=dict(state or {}),
        behavior=tuple(behavior),
        transform=transform or Transform(),
    )


def create_object(
    object_id: str,
    *,
    kind: str = "Object",
    properties: dict[str, Any] | None = None,
    transform: Transform | None = None,
) -> WorldObject:
    return WorldObject(
        id=object_id,
        kind=kind,
        properties=dict(properties or {}),
        transform=transform or Transform(),
    )


def create_relation(
    relation_id: str,
    source: str,
    target: str,
    relation_type: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> Relation:
    return Relation(
        id=relation_id,
        source=source,
        target=target,
        relation_type=relation_type,
        metadata=dict(metadata or {}),
    )


def create_event(
    event_id: str,
    event_type: str,
    *,
    target: str | None = None,
    payload: dict[str, Any] | None = None,
    tick: int = 0,
) -> Event:
    return Event(
        id=event_id,
        event_type=event_type,
        target=target,
        payload=dict(payload or {}),
        tick=tick,
    )


def add_scene(world: World, scene: Scene | str) -> World:
    next_scene = create_scene(scene) if isinstance(scene, str) else scene
    if any(existing.id == next_scene.id for existing in world.scenes):
        return world
    return World(
        name=world.name,
        scenes=world.scenes + (next_scene,),
        snapshots=world.snapshots,
        tick=world.tick,
    )


def add_entity(scene: Scene, entity: WorldEntity) -> Scene:
    if any(existing.id == entity.id for existing in scene.entities):
        return scene
    return Scene(
        id=scene.id,
        entities=scene.entities + (entity,),
        objects=scene.objects,
        relations=scene.relations,
        events=scene.events,
    )


def add_object(scene: Scene, obj: WorldObject) -> Scene:
    if any(existing.id == obj.id for existing in scene.objects):
        return scene
    return Scene(
        id=scene.id,
        entities=scene.entities,
        objects=scene.objects + (obj,),
        relations=scene.relations,
        events=scene.events,
    )


def add_relation(scene: Scene, relation: Relation) -> Scene:
    if any(existing.id == relation.id for existing in scene.relations):
        return scene
    return Scene(
        id=scene.id,
        entities=scene.entities,
        objects=scene.objects,
        relations=scene.relations + (relation,),
        events=scene.events,
    )


def add_event(scene: Scene, event: Event) -> Scene:
    if any(existing.id == event.id for existing in scene.events):
        return scene
    return Scene(
        id=scene.id,
        entities=scene.entities,
        objects=scene.objects,
        relations=scene.relations,
        events=scene.events + (event,),
    )


def replace_scene(world: World, scene: Scene) -> World:
    next_scenes = tuple(scene if existing.id == scene.id else existing for existing in world.scenes)
    return World(
        name=world.name,
        scenes=next_scenes,
        snapshots=world.snapshots,
        tick=world.tick,
    )


def snapshot(world: World, snapshot_id: str | None = None) -> Snapshot:
    snap_id = snapshot_id or f"snapshot-{len(world.snapshots)}"
    return Snapshot(
        id=snap_id,
        world_name=world.name,
        tick=world.tick,
        scenes=tuple(scene.to_dict() for scene in world.scenes),
    )


def add_snapshot(world: World, snap: Snapshot | None = None) -> World:
    next_snapshot = snap or snapshot(world)
    if any(existing.id == next_snapshot.id for existing in world.snapshots):
        return world
    return World(
        name=world.name,
        scenes=world.scenes,
        snapshots=world.snapshots + (next_snapshot,),
        tick=world.tick,
    )
