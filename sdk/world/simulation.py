"""world.simulation - deterministic World Model SDK event processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .builder import (
    Event,
    Relation,
    Scene,
    Snapshot,
    Transform,
    World,
    WorldEntity,
    WorldObject,
    add_snapshot,
    snapshot,
)
from .validation import validate_event

_PHASE4_SCHEMA = "world-model-sdk/0.4"


@dataclass(frozen=True)
class StateDelta:
    id: str
    tick: int
    target: str | None
    operation: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": _PHASE4_SCHEMA,
            "id": self.id,
            "tick": self.tick,
            "target": self.target,
            "operation": self.operation,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class WorldDelta:
    tick: int
    deltas: tuple[StateDelta, ...] = field(default_factory=tuple)
    trace: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": _PHASE4_SCHEMA,
            "tick": self.tick,
            "deltas": [delta.to_dict() for delta in self.deltas],
            "trace": list(self.trace),
        }


@dataclass(frozen=True)
class CompositeTransition:
    id: str
    event_type: str
    deltas: tuple[StateDelta, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": _PHASE4_SCHEMA,
            "id": self.id,
            "event_type": self.event_type,
            "deltas": [delta.to_dict() for delta in self.deltas],
        }


@dataclass(frozen=True)
class SimulationTrace:
    tick: int
    events: tuple[Event, ...] = field(default_factory=tuple)
    deltas: tuple[StateDelta, ...] = field(default_factory=tuple)
    snapshots: tuple[Snapshot, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": _PHASE4_SCHEMA,
            "tick": self.tick,
            "events": [event.to_dict() for event in self.events],
            "deltas": [delta.to_dict() for delta in self.deltas],
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
        }


@dataclass(frozen=True)
class BranchSimulation:
    origin_snapshot: Snapshot
    branches: dict[str, "WorldSimulationResult"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": _PHASE4_SCHEMA,
            "origin_snapshot": self.origin_snapshot.to_dict(),
            "branches": {
                branch_id: result.to_dict() for branch_id, result in sorted(self.branches.items())
            },
        }


@dataclass(frozen=True)
class WorldSimulationResult:
    world: World
    snapshot: Snapshot
    processed_events: tuple[str, ...]
    trace: tuple[str, ...]
    world_delta: WorldDelta | None = None
    simulation_trace: SimulationTrace | None = None
    origin_world: World | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "world": self.world.to_dict(),
            "snapshot": self.snapshot.to_dict(),
            "processed_events": list(self.processed_events),
            "trace": list(self.trace),
        }
        if self.world_delta is not None:
            data["schema"] = _PHASE4_SCHEMA
            data["world_deltas"] = [self.world_delta.to_dict()]
        if self.simulation_trace is not None:
            data["schema"] = _PHASE4_SCHEMA
            data["simulation_trace"] = self.simulation_trace.to_dict()
        data.setdefault("branches", [])
        return data


def create_delta(
    delta_id: str,
    tick: int,
    target: str | None,
    operation: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> StateDelta:
    return StateDelta(
        id=delta_id,
        tick=tick,
        target=target,
        operation=operation,
        before=_copy_mapping(before),
        after=_copy_mapping(after),
    )


def create_world_delta(
    tick: int,
    deltas: tuple[StateDelta, ...] | list[StateDelta] = (),
    *,
    trace: tuple[str, ...] | list[str] = (),
) -> WorldDelta:
    return WorldDelta(tick=tick, deltas=tuple(deltas), trace=tuple(trace))


def merge_deltas(*world_deltas: WorldDelta) -> WorldDelta:
    if not world_deltas:
        return WorldDelta(tick=0)
    tick = max(delta.tick for delta in world_deltas)
    deltas: list[StateDelta] = []
    traces: list[str] = []
    seen: set[str] = set()
    for world_delta in sorted(world_deltas, key=lambda item: (item.tick, item.trace)):
        for delta in world_delta.deltas:
            if delta.id not in seen:
                seen.add(delta.id)
                deltas.append(delta)
        traces.extend(world_delta.trace)
    return WorldDelta(tick=tick, deltas=tuple(deltas), trace=tuple(traces))


def validate_delta(delta: StateDelta | WorldDelta) -> bool:
    if isinstance(delta, WorldDelta):
        return delta.tick >= 0 and all(validate_delta(item) for item in delta.deltas)
    if not delta.id or delta.tick < 0 or not delta.operation:
        return False
    if delta.before == delta.after:
        return delta.operation in {"event_acknowledged", "relation_removed"}
    return True


def composite_transition(
    transition_id: str,
    event_type: str,
    deltas: tuple[StateDelta, ...] | list[StateDelta],
) -> CompositeTransition:
    return CompositeTransition(transition_id, event_type, tuple(deltas))


def expand_event(event: Event) -> tuple[Event, ...]:
    payload_events = event.payload.get("events")
    if isinstance(payload_events, (list, tuple)):
        expanded: list[Event] = []
        for index, item in enumerate(payload_events):
            if not isinstance(item, dict):
                continue
            expanded.append(
                Event(
                    id=item.get("id", f"{event.id}:{index}"),
                    event_type=item.get("event_type", event.event_type),
                    target=item.get("target", event.target),
                    payload=dict(item.get("payload", {})),
                    tick=item.get("tick", event.tick),
                )
            )
        return tuple(expanded) or (event,)
    if event.event_type == "move_to_room":
        target_room = event.payload.get("room_id")
        return (
            Event(f"{event.id}:leave", "modify", event.target, {"room_id": None}, event.tick),
            Event(f"{event.id}:enter", "modify", event.target, {"room_id": target_room}, event.tick),
        )
    return (event,)


def generate_delta(world: World, event: Event, *, tick: int | None = None) -> WorldDelta:
    next_tick = world.tick + 1 if tick is None else tick
    scene = _event_scene(world, event)
    before_item = _find_item(scene, event.target) if scene is not None and event.target else None
    trace = [f"validate:{event.id}", f"expand:{event.id}", f"delta:{event.id}"]
    deltas: list[StateDelta] = []

    if event.event_type == "create":
        item_id = event.payload.get("id")
        item_type = event.payload.get("world_item_type", "object")
        after = _created_item_dict(event)
        deltas.append(create_delta(f"{event.id}:create", next_tick, item_id, f"{item_type}_created", after=after))
    elif event.event_type == "destroy" and before_item is not None:
        operation = "entity_destroyed" if before_item.get("world_item_type") == "entity" else "object_destroyed"
        deltas.append(create_delta(f"{event.id}:destroy", next_tick, event.target, operation, before=before_item))
    elif event.event_type == "move" and before_item is not None:
        after = dict(before_item)
        after["transform"] = _payload_transform(event.payload).to_dict()
        deltas.append(create_delta(f"{event.id}:move", next_tick, event.target, "object_moved", before=before_item, after=after))
    elif event.event_type == "modify" and before_item is not None:
        after = _modified_item_dict(before_item, event.payload)
        deltas.append(
            create_delta(f"{event.id}:modify", next_tick, event.target, "property_modified", before=before_item, after=after)
        )
    elif event.event_type == "relation_add":
        relation = _payload_relation(event)
        deltas.append(create_delta(f"{event.id}:relation_add", next_tick, relation.id, "relation_added", after=relation.to_dict()))
    elif event.event_type == "relation_remove":
        relation_id = event.payload.get("relation_id") or event.target
        relation = _find_relation(scene, relation_id) if scene is not None else None
        deltas.append(
            create_delta(
                f"{event.id}:relation_remove",
                next_tick,
                relation_id,
                "relation_removed",
                before=relation.to_dict() if relation is not None else None,
            )
        )
    elif event.event_type == "interact":
        deltas.append(create_delta(f"{event.id}:ack", next_tick, event.target, "event_acknowledged", before={}, after={}))
    return WorldDelta(tick=next_tick, deltas=tuple(deltas), trace=tuple(trace))


def simulate_step(
    world: World,
    events: tuple[Event, ...] | list[Event] | None = None,
    *,
    snapshot_id: str | None = None,
) -> WorldSimulationResult:
    input_events = tuple(events) if events is not None else _due_events(world, world.tick + 1)
    expanded = tuple(expanded_event for event in sorted(input_events, key=lambda e: (e.tick, e.id)) for expanded_event in expand_event(event))
    item_ids = _world_item_ids(world)
    if not all(_validate_pipeline_event(event, item_ids) for event in expanded):
        raise ValueError("invalid event for world simulation pipeline")

    generated = tuple(generate_delta(world, event, tick=world.tick + 1) for event in expanded)
    world_delta = merge_deltas(*generated) if generated else WorldDelta(tick=world.tick + 1)
    if not validate_delta(world_delta):
        raise ValueError("invalid generated world delta")

    next_world = apply_delta(world, world_delta, processed_events=tuple(event.id for event in input_events))
    snap = snapshot(next_world, snapshot_id or f"snapshot-{next_world.tick}")
    snap = Snapshot(
        id=snap.id,
        world_id=snap.world_id,
        tick=snap.tick,
        world_state=snap.world_state,
        trace=tuple(world_delta.trace + (f"snapshot:{snap.id}",)),
    )
    next_world = add_snapshot(next_world, snap)
    sim_trace = SimulationTrace(tick=next_world.tick, events=expanded, deltas=world_delta.deltas, snapshots=(snap,))
    return WorldSimulationResult(
        world=next_world,
        snapshot=snap,
        processed_events=tuple(event.id for event in input_events),
        trace=tuple(world_delta.trace + (f"snapshot:{snap.id}",)),
        world_delta=world_delta,
        simulation_trace=sim_trace,
        origin_world=world,
    )


def simulate_until(world: World, tick: int, *, snapshot_id: str | None = None) -> WorldSimulationResult:
    results: list[WorldSimulationResult] = []
    next_world = world
    while next_world.tick < tick:
        result = simulate_step(next_world, snapshot_id=snapshot_id if next_world.tick + 1 == tick else None)
        results.append(result)
        next_world = result.world
    if results:
        processed = tuple(event_id for result in results for event_id in result.processed_events)
        trace_items = tuple(item for result in results for item in result.trace)
        events = tuple(event for result in results for event in trace_events(result))
        deltas = tuple(delta for result in results for delta in trace_deltas(result))
        snapshots = tuple(snapshot for result in results for snapshot in trace_snapshots(result))
        final = results[-1]
        return WorldSimulationResult(
            world=final.world,
            snapshot=final.snapshot,
            processed_events=processed,
            trace=trace_items,
            world_delta=WorldDelta(final.world.tick, deltas, trace_items),
            simulation_trace=SimulationTrace(final.world.tick, events, deltas, snapshots),
            origin_world=world,
        )
    snap = snapshot(world, snapshot_id or f"snapshot-{world.tick}")
    return WorldSimulationResult(world, snap, (), tuple(), WorldDelta(world.tick), SimulationTrace(world.tick, snapshots=(snap,)), world)


def apply_delta(world: World, world_delta: WorldDelta, *, processed_events: tuple[str, ...] = ()) -> World:
    scenes = list(world.scenes)
    for delta in world_delta.deltas:
        scenes = _apply_state_delta(scenes, delta)
    processed = set(processed_events)
    return World(
        id=world.id,
        version=world.version,
        scenes=tuple(scenes),
        events=tuple(event for event in world.events if event.id not in processed),
        snapshots=world.snapshots,
        tick=world_delta.tick,
    )


def replay(world: World, simulation_trace: SimulationTrace) -> World:
    return apply_delta(world, WorldDelta(simulation_trace.tick, simulation_trace.deltas, ("replay",)))


def simulate_branch(
    world: World,
    branch_events: dict[str, tuple[Event, ...] | list[Event]],
    *,
    snapshot_id: str | None = None,
) -> BranchSimulation:
    origin = snapshot(world, snapshot_id or f"origin-{world.tick}")
    results = {
        branch_id: simulate_step(world, tuple(events), snapshot_id=f"{origin.id}:{branch_id}")
        for branch_id, events in sorted(branch_events.items())
    }
    return BranchSimulation(origin, results)


def trace(result: WorldSimulationResult | SimulationTrace) -> SimulationTrace:
    if isinstance(result, SimulationTrace):
        return result
    if result.simulation_trace is None:
        return SimulationTrace(result.world.tick)
    return result.simulation_trace


def trace_events(value: WorldSimulationResult | SimulationTrace) -> tuple[Event, ...]:
    return trace(value).events


def trace_deltas(value: WorldSimulationResult | SimulationTrace) -> tuple[StateDelta, ...]:
    return trace(value).deltas


def trace_snapshots(value: WorldSimulationResult | SimulationTrace) -> tuple[Snapshot, ...]:
    return trace(value).snapshots


def current_tick(world: World) -> int:
    return world.tick


def world_delta(result: WorldSimulationResult) -> WorldDelta:
    return result.world_delta or WorldDelta(result.world.tick)


def branches(branch_simulation: BranchSimulation) -> dict[str, WorldSimulationResult]:
    return dict(branch_simulation.branches)


def replay_state(result: WorldSimulationResult) -> World:
    if result.origin_world is None or result.simulation_trace is None:
        return result.world
    return replay(result.origin_world, result.simulation_trace)


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


def _copy_mapping(value: dict[str, Any] | None) -> dict[str, Any] | None:
    return None if value is None else dict(value)


def _due_events(world: World, tick: int) -> tuple[Event, ...]:
    routed = []
    for event in world.events:
        if event.tick <= tick:
            routed.append(event)
    for scene in world.scenes:
        routed.extend(event for event in scene.events if event.tick <= tick)
    return tuple(sorted(routed, key=lambda event: (event.tick, event.id)))


def _validate_pipeline_event(event: Event, item_ids: set[str]) -> bool:
    if event.event_type in {"create", "destroy", "move", "modify", "interact"}:
        return validate_event(event, item_ids)
    if event.event_type == "relation_add":
        payload = event.payload
        return bool(
            event.id
            and payload.get("id")
            and payload.get("source") in item_ids
            and payload.get("target") in item_ids
            and payload.get("relation_type")
        )
    if event.event_type == "relation_remove":
        return bool(event.id and (event.target or event.payload.get("relation_id")))
    return False


def _world_item_ids(world: World) -> set[str]:
    item_ids: set[str] = set()
    for scene in world.scenes:
        item_ids.update(entity.id for entity in scene.entities)
        item_ids.update(obj.id for obj in scene.objects)
    return item_ids


def _event_scene(world: World, event: Event) -> Scene | None:
    scene_id = event.payload.get("scene_id")
    if scene_id is not None:
        for scene in world.scenes:
            if scene.id == scene_id:
                return scene
    if event.target is not None:
        for scene in world.scenes:
            if _find_item(scene, event.target) is not None or _find_relation(scene, event.target) is not None:
                return scene
    if len(world.scenes) == 1:
        return world.scenes[0]
    return None


def _find_item(scene: Scene | None, item_id: str | None) -> dict[str, Any] | None:
    if scene is None or item_id is None:
        return None
    for entity in scene.entities:
        if entity.id == item_id:
            data = entity.to_dict()
            data["world_item_type"] = "entity"
            return data
    for obj in scene.objects:
        if obj.id == item_id:
            data = obj.to_dict()
            data["world_item_type"] = "object"
            return data
    return None


def _find_relation(scene: Scene | None, relation_id: str | None) -> Relation | None:
    if scene is None or relation_id is None:
        return None
    for relation in scene.relations:
        if relation.id == relation_id:
            return relation
    return None


def _created_item_dict(event: Event) -> dict[str, Any]:
    item_type = event.payload.get("world_item_type", "object")
    item_id = event.payload.get("id")
    transform = _payload_transform(event.payload).to_dict()
    data = {
        "id": item_id,
        "kind": event.payload.get("kind", "Entity" if item_type == "entity" else "Object"),
        "transform": transform,
        "geometry": None,
        "parent_id": event.payload.get("parent_id"),
        "children": list(event.payload.get("children", ())),
        "world_item_type": item_type,
        "_scene_id": event.payload.get("scene_id"),
    }
    if item_type == "entity":
        data["state"] = dict(event.payload.get("state", {}))
        data["behavior"] = list(event.payload.get("behavior", ()))
    else:
        data["properties"] = dict(event.payload.get("properties", {}))
    return data


def _modified_item_dict(before: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    after = dict(before)
    item_type = before.get("world_item_type")
    if "position" in payload or "rotation" in payload or "scale" in payload:
        after["transform"] = _payload_transform(payload).to_dict()
    ignored = {"scene_id", "position", "rotation", "scale"}
    values = {key: value for key, value in payload.items() if key not in ignored}
    if item_type == "entity":
        state = dict(after.get("state", {}))
        state.update(values)
        after["state"] = state
    else:
        properties = dict(after.get("properties", {}))
        properties.update(values)
        after["properties"] = properties
    return after


def _payload_relation(event: Event) -> Relation:
    return Relation(
        id=event.payload.get("id"),
        source=event.payload.get("source"),
        target=event.payload.get("target"),
        relation_type=event.payload.get("relation_type"),
        metadata=dict(event.payload.get("metadata", {})),
    )


def _apply_state_delta(scenes: list[Scene], delta: StateDelta) -> list[Scene]:
    next_scenes = list(scenes)
    if delta.operation in {"entity_created", "object_created"} and delta.after is not None:
        scene_index = _target_scene_index(next_scenes, delta.after.get("_scene_id"))
        if scene_index is None:
            return next_scenes
        scene = next_scenes[scene_index]
        if delta.operation == "entity_created":
            entity = _entity_from_dict(delta.after)
            if all(existing.id != entity.id for existing in scene.entities):
                next_scenes[scene_index] = Scene(
                    id=scene.id,
                    entities=scene.entities + (entity,),
                    objects=scene.objects,
                    relations=scene.relations,
                    events=scene.events,
                )
        else:
            obj = _object_from_dict(delta.after)
            if all(existing.id != obj.id for existing in scene.objects):
                next_scenes[scene_index] = Scene(
                    id=scene.id,
                    entities=scene.entities,
                    objects=scene.objects + (obj,),
                    relations=scene.relations,
                    events=scene.events,
                )
        return next_scenes

    if delta.operation in {"entity_destroyed", "object_destroyed"} and delta.target is not None:
        for index, scene in enumerate(next_scenes):
            entities = tuple(entity for entity in scene.entities if entity.id != delta.target)
            objects = tuple(obj for obj in scene.objects if obj.id != delta.target)
            relations = tuple(
                relation
                for relation in scene.relations
                if relation.source != delta.target and relation.target != delta.target
            )
            if len(entities) != len(scene.entities) or len(objects) != len(scene.objects):
                next_scenes[index] = Scene(scene.id, entities, objects, relations, scene.events)
        return next_scenes

    if delta.operation in {"object_moved", "property_modified"} and delta.after is not None:
        for index, scene in enumerate(next_scenes):
            entities = tuple(
                _entity_from_dict(delta.after) if entity.id == delta.target and delta.after.get("world_item_type") == "entity" else entity
                for entity in scene.entities
            )
            objects = tuple(
                _object_from_dict(delta.after) if obj.id == delta.target and delta.after.get("world_item_type") != "entity" else obj
                for obj in scene.objects
            )
            next_scenes[index] = Scene(scene.id, entities, objects, scene.relations, scene.events)
        return next_scenes

    if delta.operation == "relation_added" and delta.after is not None:
        relation = Relation(
            id=delta.after["id"],
            source=delta.after["source"],
            target=delta.after["target"],
            relation_type=delta.after["relation_type"],
            metadata=dict(delta.after.get("metadata", {})),
        )
        scene_index = _target_scene_index(next_scenes, None, relation.source)
        if scene_index is not None:
            scene = next_scenes[scene_index]
            if all(existing.id != relation.id for existing in scene.relations):
                next_scenes[scene_index] = Scene(
                    scene.id,
                    scene.entities,
                    scene.objects,
                    scene.relations + (relation,),
                    scene.events,
                )
        return next_scenes

    if delta.operation == "relation_removed" and delta.target is not None:
        for index, scene in enumerate(next_scenes):
            relations = tuple(relation for relation in scene.relations if relation.id != delta.target)
            if len(relations) != len(scene.relations):
                next_scenes[index] = Scene(scene.id, scene.entities, scene.objects, relations, scene.events)
        return next_scenes

    return next_scenes


def _target_scene_index(scenes: list[Scene], scene_id: str | None, item_id: str | None = None) -> int | None:
    if scene_id is not None:
        for index, scene in enumerate(scenes):
            if scene.id == scene_id:
                return index
    if item_id is not None:
        for index, scene in enumerate(scenes):
            if _find_item(scene, item_id) is not None:
                return index
    if len(scenes) == 1:
        return 0
    return None


def _transform_from_dict(data: dict[str, Any]) -> Transform:
    transform = data.get("transform", {})
    return Transform(
        position=tuple(transform.get("position", (0.0, 0.0, 0.0))),
        rotation=tuple(transform.get("rotation", (0.0, 0.0, 0.0))),
        scale=tuple(transform.get("scale", (1.0, 1.0, 1.0))),
    )


def _entity_from_dict(data: dict[str, Any]) -> WorldEntity:
    return WorldEntity(
        id=data["id"],
        kind=data.get("kind", "Entity"),
        state=dict(data.get("state", {})),
        behavior=tuple(data.get("behavior", ())),
        transform=_transform_from_dict(data),
        parent_id=data.get("parent_id"),
        children=tuple(data.get("children", ())),
    )


def _object_from_dict(data: dict[str, Any]) -> WorldObject:
    return WorldObject(
        id=data["id"],
        kind=data.get("kind", "Object"),
        properties=dict(data.get("properties", {})),
        transform=_transform_from_dict(data),
        parent_id=data.get("parent_id"),
        children=tuple(data.get("children", ())),
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
        geometry=entity.geometry,
        parent_id=entity.parent_id,
        children=entity.children,
    )


def _replace_object_transform(obj: WorldObject, transform: Transform) -> WorldObject:
    return WorldObject(
        id=obj.id,
        kind=obj.kind,
        properties=obj.properties,
        transform=transform,
        geometry=obj.geometry,
        parent_id=obj.parent_id,
        children=obj.children,
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
        geometry=entity.geometry,
        parent_id=entity.parent_id,
        children=entity.children,
    )


def _merge_object_properties(obj: WorldObject, payload: dict[str, Any]) -> WorldObject:
    next_properties = dict(obj.properties)
    next_properties.update(payload)
    return WorldObject(
        id=obj.id,
        kind=obj.kind,
        properties=next_properties,
        transform=obj.transform,
        geometry=obj.geometry,
        parent_id=obj.parent_id,
        children=obj.children,
    )
