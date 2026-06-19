"""World SDK Phase 1 Conformance Tests - WSDK1-001 through WSDK1-009."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sdk import world


class WSDK1001WorldCreation(unittest.TestCase):
    """WSDK1-001: World creation and scene management."""

    def test_create_world(self):
        w = world.create_world("alpha")
        self.assertEqual(w.name, "alpha")
        self.assertEqual(w.scenes, ())

    def test_add_scene(self):
        w = world.create_world("alpha")
        w = world.add_scene(w, "room")
        self.assertEqual(world.scene_ids(w), ["room"])

    def test_add_scene_does_not_mutate_original(self):
        w = world.create_world("alpha")
        world.add_scene(w, "room")
        self.assertEqual(world.scene_ids(w), [])

    def test_duplicate_scene_ignored(self):
        w = world.create_world("alpha")
        w = world.add_scene(w, "room")
        w = world.add_scene(w, "room")
        self.assertEqual(world.scene_ids(w), ["room"])


class WSDK1002SceneStorage(unittest.TestCase):
    """WSDK1-002: Scene entity and object storage."""

    def test_add_entity(self):
        scene = world.create_scene("room")
        scene = world.add_entity(scene, world.create_entity("person", kind="Person"))
        self.assertEqual(world.entity_ids(scene), ["person"])

    def test_add_object(self):
        scene = world.create_scene("room")
        scene = world.add_object(scene, world.create_object("chair", kind="Chair"))
        self.assertEqual(world.object_ids(scene), ["chair"])

    def test_storage_does_not_mutate_original(self):
        scene = world.create_scene("room")
        world.add_object(scene, world.create_object("chair"))
        self.assertEqual(world.object_ids(scene), [])


class WSDK1003Transform(unittest.TestCase):
    """WSDK1-003: Transform support."""

    def test_create_transform(self):
        transform = world.create_transform(position=(1.0, 2.0, 3.0))
        self.assertEqual(transform.position, (1.0, 2.0, 3.0))

    def test_transform_serializes(self):
        transform = world.create_transform(rotation=(0.0, 90.0, 0.0))
        self.assertEqual(transform.to_dict()["rotation"], [0.0, 90.0, 0.0])

    def test_transform_validates(self):
        self.assertTrue(world.validate_transform(world.create_transform()))


class WSDK1004Relations(unittest.TestCase):
    """WSDK1-004: World-level relations."""

    def test_add_relation(self):
        scene = world.create_scene("room")
        scene = world.add_entity(scene, world.create_entity("person"))
        scene = world.add_object(scene, world.create_object("chair"))
        scene = world.add_relation(
            scene,
            world.create_relation("r1", "person", "chair", "near"),
        )
        self.assertEqual(world.relation_ids(scene), ["r1"])

    def test_relation_has_reason_graph_shape(self):
        relation = world.create_relation("r1", "a", "b", "connected_to")
        d = relation.to_dict()
        self.assertEqual(d["reason_graph_relation"]["from"], "a")
        self.assertEqual(d["reason_graph_relation"]["to"], "b")


class WSDK1005Events(unittest.TestCase):
    """WSDK1-005: Event representation and storage."""

    def test_create_event(self):
        event = world.create_event("e1", "move", target="person")
        self.assertEqual(event.event_type, "move")

    def test_add_event(self):
        scene = world.create_scene("room")
        scene = world.add_entity(scene, world.create_entity("person"))
        scene = world.add_event(scene, world.create_event("e1", "interact", target="person"))
        self.assertEqual(world.event_ids(scene), ["e1"])


class WSDK1006Validation(unittest.TestCase):
    """WSDK1-006: World SDK validation."""

    def _valid_world(self):
        scene = world.create_scene("room")
        scene = world.add_entity(scene, world.create_entity("person"))
        scene = world.add_object(scene, world.create_object("door"))
        scene = world.add_relation(scene, world.create_relation("r1", "person", "door", "near"))
        w = world.create_world("building")
        return world.add_scene(w, scene)

    def test_valid_world_passes(self):
        self.assertTrue(world.validate(self._valid_world()))

    def test_valid_world_dict_passes(self):
        self.assertTrue(world.validate(self._valid_world().to_dict()))

    def test_relation_to_missing_target_fails(self):
        scene = world.create_scene("room")
        scene = world.add_entity(scene, world.create_entity("person"))
        scene = world.add_relation(scene, world.create_relation("r1", "person", "missing", "near"))
        w = world.add_scene(world.create_world("building"), scene)
        self.assertFalse(world.validate(w))

    def test_event_to_missing_target_fails(self):
        scene = world.create_scene("room")
        scene = world.add_event(scene, world.create_event("e1", "move", target="missing"))
        w = world.add_scene(world.create_world("building"), scene)
        self.assertFalse(world.validate(w))


class WSDK1007Snapshot(unittest.TestCase):
    """WSDK1-007: Snapshot production."""

    def test_snapshot(self):
        w = world.add_scene(world.create_world("building"), "room")
        snap = world.snapshot(w, "s0")
        self.assertEqual(snap.id, "s0")
        self.assertEqual(snap.world_name, "building")

    def test_add_snapshot(self):
        w = world.add_scene(world.create_world("building"), "room")
        w = world.add_snapshot(w, world.snapshot(w, "s0"))
        self.assertEqual(world.snapshot_ids(w), ["s0"])

    def test_snapshot_serializable(self):
        w = world.add_scene(world.create_world("building"), "room")
        snap = world.snapshot(w)
        self.assertEqual(snap.to_dict()["schema_version"], "world-sdk/0.1")


class WSDK1008Simulation(unittest.TestCase):
    """WSDK1-008: Deterministic simulation."""

    def _moving_world(self):
        scene = world.create_scene("room")
        scene = world.add_entity(scene, world.create_entity("person"))
        scene = world.add_event(
            scene,
            world.create_event(
                "e1",
                "move",
                target="person",
                payload={"position": (4.0, 5.0, 6.0)},
            ),
        )
        return world.add_scene(world.create_world("building"), scene)

    def test_simulate_processes_event(self):
        result = world.simulate(self._moving_world(), snapshot_id="s1")
        self.assertEqual(result.processed_events, ("e1",))

    def test_simulate_moves_entity(self):
        result = world.simulate(self._moving_world(), snapshot_id="s1")
        entity = result.world.scenes[0].entities[0]
        self.assertEqual(entity.transform.position, (4.0, 5.0, 6.0))

    def test_simulate_produces_snapshot(self):
        result = world.simulate(self._moving_world(), snapshot_id="s1")
        self.assertEqual(result.snapshot.id, "s1")
        self.assertEqual(world.snapshot_ids(result.world), ["s1"])

    def test_simulation_is_deterministic(self):
        r1 = world.simulate(self._moving_world(), snapshot_id="s1")
        r2 = world.simulate(self._moving_world(), snapshot_id="s1")
        self.assertEqual(r1.to_dict(), r2.to_dict())

    def test_simulate_creates_object(self):
        scene = world.create_scene("room")
        scene = world.add_event(
            scene,
            world.create_event(
                "e1",
                "create",
                payload={
                    "id": "table",
                    "world_item_type": "object",
                    "kind": "Table",
                    "position": (1.0, 0.0, 0.0),
                },
            ),
        )
        w = world.add_scene(world.create_world("building"), scene)
        result = world.simulate(w, snapshot_id="s1")
        self.assertEqual(world.object_ids(result.world.scenes[0]), ["table"])


class WSDK1009EndToEndWorkflow(unittest.TestCase):
    """WSDK1-009: End-to-end World SDK workflow."""

    def test_world_sdk_workflow(self):
        scene = world.create_scene("city")
        scene = world.add_entity(
            scene,
            world.create_entity("agent", kind="Agent", state={"mode": "idle"}),
        )
        scene = world.add_object(scene, world.create_object("door", kind="Door"))
        scene = world.add_relation(scene, world.create_relation("rel1", "agent", "door", "near"))
        scene = world.add_event(
            scene,
            world.create_event("evt1", "modify", target="agent", payload={"mode": "active"}),
        )
        w = world.add_scene(world.create_world("simulation"), scene)

        self.assertTrue(world.validate(w))
        result = world.simulate(w, snapshot_id="after-evt1")

        self.assertTrue(world.validate(result.world))
        self.assertEqual(result.world.scenes[0].entities[0].state["mode"], "active")
        self.assertEqual(result.snapshot.id, "after-evt1")


if __name__ == "__main__":
    unittest.main()
