"""world.simulation - deterministic World Model SDK Phase 1 event processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .builder import (
    Event,
    Scene,
    Snapshot,
    Transform,
    World,
    WorldEntity,
    WorldObject,
    add_snapshot,
    snapshot,
)


@dataclass(frozen=True)
class WorldSimulationResult:
    world: World
    snapshot: Snapshot
    processed_events: tuple[str, ...]
    trace: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "world": self.world.to_dict(),
            "snapshot": self.snapshot.to_dict(),
            "processed_events": list(self.processed_events),
            "trace": list(self.trace),
        }


def simulate(world: World, *, steps: int = 1, snapshot_id: str | None = None) -> WorldSimulationResult:
    """Run deterministic event processing and return the next world plus snapshot."""
    next_world = world
    processed: list[str] = []
    trace: list[str] = []
    for _ in range(max(0, steps)):
        next_scenes = []
        routed_world_events = _route_world_events(next_world)
        for scene in next_world.scenes:
            next_scene, scene_processed, scene_trace = _process_scene(
                scene,
                next_world.tick + 1,
                routed_world_events.get(scene.id, ()),
            )
            next_scenes.append(next_scene)
            processed.extend(scene_processed)
            trace.extend(scene_trace)
        next_world = World(
            id=next_world.id,
            version=next_world.version,
            scenes=tuple(next_scenes),
            events=tuple(event for event in next_world.events if event.id not in set(processed)),
            snapshots=next_world.snapshots,
            tick=next_world.tick + 1,
        )

    snap = snapshot(next_world, snapshot_id)
    snap = Snapshot(
        id=snap.id,
        world_id=snap.world_id,
        tick=snap.tick,
        world_state=snap.world_state,
        trace=tuple(trace + [f"snapshot:{snap.id}"]),
    )
    next_world = add_snapshot(next_world, snap)
    return WorldSimulationResult(
        world=next_world,
        snapshot=snap,
        processed_events=tuple(processed),
        trace=tuple(trace + [f"snapshot:{snap.id}"]),
    )


def _route_world_events(world: World) -> dict[str, tuple[Event, ...]]:
    routes: dict[str, list[Event]] = {scene.id: [] for scene in world.scenes}
    for event in world.events:
        scene_id = event.payload.get("scene_id")
        if scene_id in routes:
            routes[scene_id].append(event)
        elif len(world.scenes) == 1:
            routes[world.scenes[0].id].append(event)
    return {scene_id: tuple(events) for scene_id, events in routes.items()}


def _process_scene(
    scene: Scene,
    tick: int,
    routed_events: tuple[Event, ...] = (),
) -> tuple[Scene, list[str], list[str]]:
    entities = list(scene.entities)
    objects = list(scene.objects)
    relations = list(scene.relations)
    processed: list[str] = []
    trace: list[str] = []

    scene_events = scene.events + routed_events
    for event in sorted(scene_events, key=lambda e: (e.tick, e.id)):
        if event.tick > tick:
            continue
        processed.append(event.id)
        trace.append(f"{scene.id}:{event.event_type}:{event.id}")
        entities, objects, relations = _apply_event(event, entities, objects, relations)

    return (
        Scene(
            id=scene.id,
            entities=tuple(entities),
            objects=tuple(objects),
            relations=tuple(relations),
            events=tuple(event for event in scene.events if event.id not in set(processed)),
        ),
        processed,
        trace,
    )


def _apply_event(
    event: Event,
    entities: list[WorldEntity],
    objects: list[WorldObject],
    relations: list,
) -> tuple[list[WorldEntity], list[WorldObject], list]:
    if event.event_type == "move" and event.target:
        transform = _payload_transform(event.payload)
        entities = [
            entity if entity.id != event.target else _replace_entity_transform(entity, transform)
            for entity in entities
        ]
        objects = [
            obj if obj.id != event.target else _replace_object_transform(obj, transform)
            for obj in objects
        ]
    elif event.event_type == "modify" and event.target:
        entities = [
            entity if entity.id != event.target else _merge_entity_state(entity, event.payload)
            for entity in entities
        ]
        objects = [
            obj if obj.id != event.target else _merge_object_properties(obj, event.payload)
            for obj in objects
        ]
    elif event.event_type == "destroy" and event.target:
        entities = [entity for entity in entities if entity.id != event.target]
        objects = [obj for obj in objects if obj.id != event.target]
        relations = [
            relation
            for relation in relations
            if relation.source != event.target and relation.target != event.target
        ]
    elif event.event_type == "create":
        item_id = event.payload.get("id")
        item_type = event.payload.get("world_item_type", "object")
        if item_id and item_type == "entity" and all(entity.id != item_id for entity in entities):
            entities.append(
                WorldEntity(
                    id=item_id,
                    kind=event.payload.get("kind", "Entity"),
                    state=dict(event.payload.get("state", {})),
                    behavior=tuple(event.payload.get("behavior", ())),
                    transform=_payload_transform(event.payload),
                )
            )
        elif item_id and item_type == "object" and all(obj.id != item_id for obj in objects):
            objects.append(
                WorldObject(
                    id=item_id,
                    kind=event.payload.get("kind", "Object"),
                    properties=dict(event.payload.get("properties", {})),
                    transform=_payload_transform(event.payload),
                )
            )
    return entities, objects, relations


def _payload_transform(payload: dict[str, Any]) -> Transform:
    return Transform(
        position=tuple(payload.get("position", (0.0, 0.0, 0.0))),
        rotation=tuple(payload.get("rotation", (0.0, 0.0, 0.0))),
        scale=tuple(payload.get("scale", (1.0, 1.0, 1.0))),
    )


def _replace_entity_transform(entity: WorldEntity, transform: Transform) -> WorldEntity:
    return WorldEntity(
        id=entity.id,
        kind=entity.kind,
        state=entity.state,
        behavior=entity.behavior,
        transform=transform,
    )


def _replace_object_transform(obj: WorldObject, transform: Transform) -> WorldObject:
    return WorldObject(
        id=obj.id,
        kind=obj.kind,
        properties=obj.properties,
        transform=transform,
    )


def _merge_entity_state(entity: WorldEntity, payload: dict[str, Any]) -> WorldEntity:
    next_state = dict(entity.state)
    next_state.update(payload)
    return WorldEntity(
        id=entity.id,
        kind=entity.kind,
        state=next_state,
        behavior=entity.behavior,
        transform=entity.transform,
    )


def _merge_object_properties(obj: WorldObject, payload: dict[str, Any]) -> WorldObject:
    next_properties = dict(obj.properties)
    next_properties.update(payload)
    return WorldObject(
        id=obj.id,
        kind=obj.kind,
        properties=next_properties,
        transform=obj.transform,
    )
