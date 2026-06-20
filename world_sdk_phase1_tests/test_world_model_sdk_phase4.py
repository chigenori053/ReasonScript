"""World Model SDK Phase 4 conformance tests - WM4-001 through WM4-020."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend.runtime_integration import RuntimeValue
from sdk import world


class WorldModelSDKPhase4Conformance(unittest.TestCase):
    def _world(self):
        scene = world.create_scene("room")
        scene = world.add_entity(scene, world.create_entity("agent", kind="Agent", state={"room_id": "hall"}))
        scene = world.add_object(scene, world.create_object("door", kind="Door", properties={"open": False}))
        return world.add_scene(world.create_world("dynamic-world"), scene)

    def _move_event(self, event_id="move-agent", position=(2.0, 0.0, 0.0)):
        return world.create_event(
            event_id,
            "move",
            target="agent",
            payload={"scene_id": "room", "position": position},
        )

    def test_wm4_001_state_delta_creation(self):
        delta = world.create_delta("d1", 1, "agent", "property_modified", before={"x": 0}, after={"x": 1})
        self.assertEqual(delta.id, "d1")
        self.assertEqual(delta.to_dict()["schema"], "world-model-sdk/0.4")

    def test_wm4_002_world_delta_creation(self):
        delta = world.create_delta("d1", 1, "agent", "property_modified", before={"x": 0}, after={"x": 1})
        world_delta = world.create_world_delta(1, (delta,), trace=("delta:d1",))
        self.assertEqual(world_delta.deltas, (delta,))
        self.assertEqual(world_delta.trace, ("delta:d1",))

    def test_wm4_003_delta_validation(self):
        delta = world.create_delta("d1", 1, "agent", "property_modified", before={"x": 0}, after={"x": 1})
        self.assertTrue(world.validate_delta(delta))
        self.assertFalse(world.validate_delta(world.create_delta("", -1, "agent", "", before={}, after={})))

    def test_wm4_004_composite_transition(self):
        delta = world.create_delta("d1", 1, "agent", "object_moved", before={"x": 0}, after={"x": 1})
        transition = world.composite_transition("move-character", "MoveCharacter", (delta,))
        self.assertEqual([item.operation for item in transition.deltas], ["object_moved"])

    def test_wm4_005_event_validation(self):
        self.assertTrue(world.validate_event(self._move_event(), {"agent"}))
        with self.assertRaises(ValueError):
            world.simulate_step(self._world(), (world.create_event("bad", "unknown"),))

    def test_wm4_006_event_expansion(self):
        event = world.create_event("move-room", "move_to_room", target="agent", payload={"room_id": "kitchen"})
        expanded = world.expand_event(event)
        self.assertEqual([item.id for item in expanded], ["move-room:leave", "move-room:enter"])

    def test_wm4_007_delta_generation(self):
        world_delta = world.generate_delta(self._world(), self._move_event())
        self.assertEqual(world_delta.tick, 1)
        self.assertEqual(world_delta.deltas[0].operation, "object_moved")

    def test_wm4_008_delta_application(self):
        w = self._world()
        applied = world.apply_delta(w, world.generate_delta(w, self._move_event()))
        self.assertEqual(applied.scenes[0].entities[0].transform.position, (2.0, 0.0, 0.0))
        self.assertEqual(world.current_tick(applied), 1)

    def test_wm4_009_snapshot_generation(self):
        result = world.simulate_step(self._world(), (self._move_event(),), snapshot_id="s1")
        self.assertEqual(result.snapshot.id, "s1")
        self.assertEqual(result.snapshot.tick, 1)

    def test_wm4_010_simulation_trace_generation(self):
        result = world.simulate_step(self._world(), (self._move_event(),))
        self.assertEqual(world.trace(result).tick, 1)
        self.assertEqual([event.id for event in world.trace_events(result)], ["move-agent"])
        self.assertTrue(world.trace_deltas(result))

    def test_wm4_011_replay(self):
        w = self._world()
        result = world.simulate_step(w, (self._move_event(),))
        replayed = world.replay(w, world.trace(result))
        self.assertEqual(replayed.to_dict(), result.world.to_dict() | {"snapshots": []})

    def test_wm4_012_replay_determinism(self):
        w = self._world()
        result = world.simulate_step(w, (self._move_event(),))
        self.assertEqual(world.replay(w, world.trace(result)).to_dict(), world.replay(w, world.trace(result)).to_dict())

    def test_wm4_013_branch_simulation(self):
        branches = world.simulate_branch(
            self._world(),
            {
                "a": (self._move_event("a", (1.0, 0.0, 0.0)),),
                "b": (self._move_event("b", (3.0, 0.0, 0.0)),),
            },
        )
        self.assertEqual(set(world.branches(branches)), {"a", "b"})

    def test_wm4_014_branch_isolation(self):
        branch_result = world.simulate_branch(
            self._world(),
            {
                "a": (self._move_event("a", (1.0, 0.0, 0.0)),),
                "b": (self._move_event("b", (3.0, 0.0, 0.0)),),
            },
        )
        results = world.branches(branch_result)
        self.assertEqual(results["a"].world.scenes[0].entities[0].transform.position, (1.0, 0.0, 0.0))
        self.assertEqual(results["b"].world.scenes[0].entities[0].transform.position, (3.0, 0.0, 0.0))

    def test_wm4_015_delta_merge(self):
        d1 = world.create_delta("a", 1, "agent", "property_modified", before={"x": 0}, after={"x": 1})
        d2 = world.create_delta("b", 1, "door", "property_modified", before={"open": False}, after={"open": True})
        merged = world.merge_deltas(world.create_world_delta(1, (d1,)), world.create_world_delta(1, (d2,)))
        self.assertEqual([delta.id for delta in merged.deltas], ["a", "b"])

    def test_wm4_016_trace_query(self):
        result = world.simulate_step(self._world(), (self._move_event(),))
        self.assertEqual(world.trace_snapshots(result)[0].tick, 1)
        self.assertEqual(world.world_delta(result).tick, 1)

    def test_wm4_017_serialization(self):
        payload = world.to_json(world.simulate_step(self._world(), (self._move_event(),)).to_dict())
        self.assertIn('"schema":"world-model-sdk/0.4"', payload)
        self.assertIn('"world_deltas":[', payload)
        self.assertIn('"simulation_trace":{', payload)
        self.assertIn('"branches":[]', payload)

    def test_wm4_018_runtime_compatibility(self):
        value = world.runtime_value(world.simulate_step(self._world(), (self._move_event(),)).world)
        self.assertIsInstance(value, RuntimeValue)
        self.assertEqual(value.kind, "WorldModelValue")

    def test_wm4_019_deterministic_simulation(self):
        w = self._world()
        self.assertEqual(
            world.simulate_step(w, (self._move_event(),), snapshot_id="s1").to_dict(),
            world.simulate_step(w, (self._move_event(),), snapshot_id="s1").to_dict(),
        )

    def test_wm4_020_end_to_end_world_evolution(self):
        result = world.simulate_until(world.add_event(self._world(), self._move_event()), 1, snapshot_id="s-final")
        self.assertEqual(result.world.tick, 1)
        self.assertEqual(result.world.scenes[0].entities[0].transform.position, (2.0, 0.0, 0.0))
        self.assertEqual(result.processed_events, ("move-agent",))


if __name__ == "__main__":
    unittest.main()
