"""World Model SDK Phase 1 conformance tests - WM1-001 through WM1-018."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend.runtime_integration import RuntimeValue
from sdk import world


class WorldModelSDKConformance(unittest.TestCase):
    def _scene(self):
        scene = world.create_scene("room")
        scene = world.add_entity(scene, world.create_entity("agent", kind="Agent"))
        scene = world.add_object(scene, world.create_object("door", kind="Door"))
        return world.add_relation(scene, world.create_relation("rel1", "agent", "door", "near"))

    def _world(self):
        return world.add_scene(world.create_world("world-a"), self._scene())

    def test_wm1_001_world_creation(self):
        w = world.create_world("world-a")
        self.assertEqual(w.id, "world-a")
        self.assertEqual(w.version, "0.1")
        self.assertEqual(w.events, ())

    def test_wm1_002_scene_creation(self):
        scene = world.create_scene("room")
        self.assertEqual(scene.id, "room")
        self.assertEqual(scene.entities, ())

    def test_wm1_003_entity_creation(self):
        entity = world.create_entity("agent", state={"mode": "idle"})
        self.assertEqual(entity.id, "agent")
        self.assertEqual(entity.state["mode"], "idle")

    def test_wm1_004_object_creation(self):
        obj = world.create_object("door", properties={"open": False})
        self.assertEqual(obj.id, "door")
        self.assertFalse(obj.properties["open"])

    def test_wm1_005_transform_creation(self):
        transform = world.create_transform(position=(1.0, 2.0, 3.0))
        self.assertEqual(transform.to_dict()["position"], [1.0, 2.0, 3.0])
        self.assertTrue(world.validate_transform(transform))

    def test_wm1_006_relation_creation(self):
        relation = world.create_relation("rel1", "agent", "door", "near")
        self.assertEqual(relation.relation_type, "near")
        self.assertEqual(relation.to_dict()["reason_graph_relation"]["relation"], "near")

    def test_wm1_007_event_creation(self):
        event = world.create_event("evt1", "move", target="agent", payload={"position": (1, 0, 0)})
        self.assertEqual(event.event_type, "move")
        self.assertEqual(event.target, "agent")

    def test_wm1_008_world_validation(self):
        self.assertTrue(world.validate(self._world()))
        invalid = self._world().to_dict()
        invalid["schema"] = "wrong/0.0"
        self.assertFalse(world.validate(invalid))

    def test_wm1_009_scene_validation(self):
        self.assertTrue(world.validate_scene(self._scene()))
        invalid = self._scene().to_dict()
        invalid["entities"][0]["transform"]["position"] = [1.0, 2.0]
        self.assertFalse(world.validate_scene(invalid))

    def test_wm1_010_relation_validation(self):
        scene = world.create_scene("room")
        scene = world.add_entity(scene, world.create_entity("agent"))
        scene = world.add_relation(scene, world.create_relation("rel1", "agent", "missing", "near"))
        self.assertFalse(world.validate_scene(scene))

    def test_wm1_011_event_validation(self):
        self.assertTrue(world.validate_event(world.create_event("evt1", "interact", target="agent"), {"agent"}))
        self.assertFalse(world.validate_event(world.create_event("evt2", "unknown")))

    def test_wm1_012_snapshot_creation(self):
        snap = world.snapshot(self._world(), "s0")
        self.assertEqual(snap.id, "s0")
        self.assertEqual(snap.world_id, "world-a")
        self.assertIn("world_state", snap.to_dict())

    def test_wm1_013_simulation_execution(self):
        w = self._world()
        w = world.add_event(
            w,
            world.create_event(
                "evt1",
                "move",
                target="agent",
                payload={"scene_id": "room", "position": (5.0, 0.0, 0.0)},
            ),
        )
        result = world.simulate(w, snapshot_id="s1")
        self.assertEqual(result.world.scenes[0].entities[0].transform.position, (5.0, 0.0, 0.0))
        self.assertEqual(result.processed_events, ("evt1",))

    def test_wm1_014_deterministic_replay(self):
        w = self._world()
        w = world.add_event(w, world.create_event("b", "interact", target="agent", payload={"scene_id": "room"}))
        w = world.add_event(w, world.create_event("a", "interact", target="agent", payload={"scene_id": "room"}))
        r1 = world.simulate(w, snapshot_id="s1")
        r2 = world.simulate(w, snapshot_id="s1")
        self.assertEqual(r1.to_dict(), r2.to_dict())
        self.assertEqual(r1.processed_events, ("a", "b"))

    def test_wm1_015_serialization(self):
        payload = world.to_json(self._world())
        self.assertIn('"schema":"world-model-sdk/0.1"', payload)
        self.assertEqual(payload, world.to_json(self._world()))

    def test_wm1_016_query_api(self):
        w = self._world()
        scene = world.scenes(w)[0]
        self.assertEqual(world.scene_ids(w), ["room"])
        self.assertEqual([entity.id for entity in world.entities(scene)], ["agent"])
        self.assertEqual([obj.id for obj in world.objects(scene)], ["door"])
        self.assertEqual([relation.id for relation in world.relations(scene)], ["rel1"])
        self.assertEqual(world.snapshots(w), [])

    def test_wm1_017_immutable_mutation(self):
        w = world.create_world("world-a")
        w2 = world.add_scene(w, "room")
        self.assertEqual(world.scene_ids(w), [])
        self.assertEqual(world.scene_ids(w2), ["room"])

    def test_wm1_018_runtime_compatibility(self):
        value = world.runtime_value(self._world())
        self.assertIsInstance(value, RuntimeValue)
        self.assertEqual(value.kind, "WorldModelValue")
        self.assertEqual(world.build_world_model_metadata(), {"world_model": {"version": "0.1"}})


if __name__ == "__main__":
    unittest.main()
