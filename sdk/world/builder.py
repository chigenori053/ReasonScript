"""world.builder - construct World Model SDK Phase 1 models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_SCHEMA = "world-model-sdk/0.2"
_VERSION = "0.2"


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
    geometry: Any = None
    parent_id: str | None = None
    children: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "state": dict(self.state),
            "behavior": list(self.behavior),
            "transform": self.transform.to_dict(),
            "geometry": self.geometry.to_dict() if self.geometry is not None else None,
            "parent_id": self.parent_id,
            "children": list(self.children),
        }


@dataclass(frozen=True)
class WorldObject:
    id: str
    kind: str = "Object"
    properties: dict[str, Any] = field(default_factory=dict)
    transform: Transform = field(default_factory=Transform)
    geometry: Any = None
    parent_id: str | None = None
    children: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "properties": dict(self.properties),
            "transform": self.transform.to_dict(),
            "geometry": self.geometry.to_dict() if self.geometry is not None else None,
            "parent_id": self.parent_id,
            "children": list(self.children),
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
    world_id: str
    tick: int
    world_state: dict[str, Any]
    trace: tuple[str, ...] = field(default_factory=tuple)

    @property
    def world_name(self) -> str:
        return self.world_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": _SCHEMA,
            "schema_version": _SCHEMA,
            "id": self.id,
            "world_id": self.world_id,
            "world_name": self.world_id,
            "tick": self.tick,
            "world_state": dict(self.world_state),
            "trace": list(self.trace),
        }


@dataclass(frozen=True)
class World:
    id: str
    version: str = _VERSION
    scenes: tuple[Scene, ...] = field(default_factory=tuple)
    events: tuple[Event, ...] = field(default_factory=tuple)
    snapshots: tuple[Snapshot, ...] = field(default_factory=tuple)
    tick: int = 0

    @property
    def name(self) -> str:
        return self.id

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": _SCHEMA,
            "schema_version": _SCHEMA,
            "id": self.id,
            "name": self.id,
            "version": self.version,
            "tick": self.tick,
            "scenes": [scene.to_dict() for scene in self.scenes],
            "events": [event.to_dict() for event in self.events],
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
            "metadata": {"world_model": {"version": self.version}},
            "geometry": _world_geometry(self.scenes),
            "hierarchy": _world_hierarchy(self.scenes),
            "spatial_relations": _world_spatial_relations(self.scenes),
        }


def create_transform(
    *,
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> Transform:
    return Transform(position=position, rotation=rotation, scale=scale)


def create_world(world_id: str, *, version: str = _VERSION) -> World:
    return World(id=world_id, version=version)


def create_scene(scene_id: str) -> Scene:
    return Scene(id=scene_id)


def create_entity(
    entity_id: str,
    *,
    kind: str = "Entity",
    state: dict[str, Any] | None = None,
    behavior: tuple[str, ...] = (),
    transform: Transform | None = None,
    geometry: Any = None,
    parent_id: str | None = None,
    children: tuple[str, ...] = (),
) -> WorldEntity:
    return WorldEntity(
        id=entity_id,
        kind=kind,
        state=dict(state or {}),
        behavior=tuple(behavior),
        transform=transform or Transform(),
        geometry=geometry,
        parent_id=parent_id,
        children=tuple(children),
    )


def create_object(
    object_id: str,
    *,
    kind: str = "Object",
    properties: dict[str, Any] | None = None,
    transform: Transform | None = None,
    geometry: Any = None,
    parent_id: str | None = None,
    children: tuple[str, ...] = (),
) -> WorldObject:
    return WorldObject(
        id=object_id,
        kind=kind,
        properties=dict(properties or {}),
        transform=transform or Transform(),
        geometry=geometry,
        parent_id=parent_id,
        children=tuple(children),
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
        id=world.id,
        version=world.version,
        scenes=world.scenes + (next_scene,),
        events=world.events,
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


def add_event(container: Scene | World, event: Event) -> Scene | World:
    if isinstance(container, World):
        if any(existing.id == event.id for existing in container.events):
            return container
        return World(
            id=container.id,
            version=container.version,
            scenes=container.scenes,
            events=container.events + (event,),
            snapshots=container.snapshots,
            tick=container.tick,
        )
    if any(existing.id == event.id for existing in container.events):
        return container
    return Scene(
        id=container.id,
        entities=container.entities,
        objects=container.objects,
        relations=container.relations,
        events=container.events + (event,),
    )


def replace_scene(world: World, scene: Scene) -> World:
    next_scenes = tuple(scene if existing.id == scene.id else existing for existing in world.scenes)
    return World(
        id=world.id,
        version=world.version,
        scenes=next_scenes,
        events=world.events,
        snapshots=world.snapshots,
        tick=world.tick,
    )


def snapshot(world: World, snapshot_id: str | None = None) -> Snapshot:
    snap_id = snapshot_id or f"snapshot-{len(world.snapshots)}"
    state = {
        "id": world.id,
        "version": world.version,
        "tick": world.tick,
        "scenes": [scene.to_dict() for scene in world.scenes],
        "events": [event.to_dict() for event in world.events],
    }
    return Snapshot(
        id=snap_id,
        world_id=world.id,
        tick=world.tick,
        world_state=state,
    )


def add_snapshot(world: World, snap: Snapshot | None = None) -> World:
    next_snapshot = snap or snapshot(world)
    if any(existing.id == next_snapshot.id for existing in world.snapshots):
        return world
    return World(
        id=world.id,
        version=world.version,
        scenes=world.scenes,
        events=world.events,
        snapshots=world.snapshots + (next_snapshot,),
        tick=world.tick,
    )


def _world_geometry(scenes: tuple[Scene, ...]) -> dict[str, Any]:
    geometry: dict[str, Any] = {}
    for scene in scenes:
        for item in scene.entities + scene.objects:
            if item.geometry is not None:
                geometry[item.id] = item.geometry.to_dict()
    return geometry


def _world_hierarchy(scenes: tuple[Scene, ...]) -> dict[str, Any]:
    hierarchy: dict[str, Any] = {}
    for scene in scenes:
        for item in scene.entities + scene.objects:
            if item.parent_id is not None or item.children:
                hierarchy[item.id] = {
                    "parent": item.parent_id,
                    "children": list(item.children),
                }
    return hierarchy


def _world_spatial_relations(scenes: tuple[Scene, ...]) -> list[dict[str, Any]]:
    relation_types = {"left_of", "right_of", "above", "below", "inside", "contains", "near", "far"}
    relations: list[dict[str, Any]] = []
    for scene in scenes:
        for relation in scene.relations:
            if relation.relation_type in relation_types:
                relations.append(relation.to_dict())
    return relations
