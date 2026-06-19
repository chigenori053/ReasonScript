"""World Model SDK Phase 2 conformance tests - WM2-001 through WM2-020."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend.runtime_integration import RuntimeValue
from sdk import world


class WorldModelSDKPhase2Conformance(unittest.TestCase):
    def _spatial_scene(self):
        room_geom = world.create_geometry("g-room", "Rectangle2D", width=10.0, height=10.0)
        table_geom = world.create_geometry("g-table", "Rectangle2D", width=2.0, height=1.0)
        chair_geom = world.create_geometry("g-chair", "Circle2D", radius=0.5)
        scene = world.create_scene("room")
        scene = world.add_object(scene, world.create_object("room-object", kind="Room", geometry=room_geom))
        scene = world.add_object(scene, world.create_object("table", kind="Table", geometry=table_geom))
        scene = world.add_object(scene, world.create_object("chair", kind="Chair", geometry=chair_geom))
        scene = world.attach_child(scene, "room-object", "table")
        scene = world.attach_child(scene, "room-object", "chair")
        scene = world.add_spatial_relation(scene, "rel1", "chair", "table", "left_of")
        scene = world.add_spatial_relation(scene, "rel2", "table", "room-object", "inside")
        return scene

    def test_wm2_001_geometry_creation(self):
        geometry = world.create_geometry("g1", "Point2D", x=1.0, y=2.0)
        self.assertEqual(geometry.id, "g1")
        self.assertEqual(geometry.geometry_type, "Point2D")

    def test_wm2_002_geometry_validation(self):
        self.assertTrue(world.validate_geometry(world.create_geometry("g1", "Circle2D", radius=1.0)))
        self.assertFalse(world.validate_geometry(world.create_geometry("g2", "Circle2D")))

    def test_wm2_003_2d_geometry(self):
        self.assertTrue(world.validate_geometry(world.create_geometry("r", "Rectangle2D", width=2.0, height=3.0)))
        self.assertTrue(world.validate_geometry(world.create_geometry("t", "Triangle2D", points=[(0, 0), (1, 0), (0, 1)])))

    def test_wm2_004_3d_geometry(self):
        self.assertTrue(world.validate_geometry(world.create_geometry("c", "Cube3D", width=1.0, height=1.0, depth=1.0)))
        self.assertTrue(world.validate_geometry(world.create_geometry("s", "Sphere3D", radius=1.0)))

    def test_wm2_005_hierarchy_creation(self):
        scene = self._spatial_scene()
        self.assertEqual(world.parent(scene, "table"), "room-object")
        self.assertEqual(world.children(scene, "room-object"), ["chair", "table"])

    def test_wm2_006_hierarchy_validation(self):
        self.assertTrue(world.validate_hierarchy(self._spatial_scene()))
        scene = world.create_scene("bad")
        scene = world.add_object(scene, world.create_object("a", parent_id="missing"))
        self.assertFalse(world.validate_hierarchy(scene))

    def test_wm2_007_local_transform(self):
        transform = world.create_transform(position=(1.0, 2.0, 0.0))
        scene = world.create_scene("room")
        scene = world.add_object(scene, world.create_object("table", transform=transform))
        self.assertEqual(world.local_transform(scene, "table"), transform)

    def test_wm2_008_world_transform(self):
        parent_t = world.create_transform(position=(10.0, 0.0, 0.0))
        child_t = world.create_transform(position=(1.0, 2.0, 0.0))
        scene = world.create_scene("room")
        scene = world.add_object(scene, world.create_object("room-object", transform=parent_t))
        scene = world.add_object(scene, world.create_object("table", transform=child_t))
        scene = world.attach_child(scene, "room-object", "table")
        self.assertEqual(world.world_transform(scene, "table").position, (11.0, 2.0, 0.0))

    def test_wm2_009_spatial_relation_creation(self):
        scene = self._spatial_scene()
        self.assertEqual([r.relation_type for r in world.spatial_relations(scene)], ["left_of", "inside"])

    def test_wm2_010_spatial_relation_validation(self):
        self.assertTrue(world.validate_spatial_relations(self._spatial_scene()))
        bad = world.create_scene("bad")
        bad = world.add_spatial_relation(bad, "r", "a", "b", "left_of")
        self.assertFalse(world.validate_spatial_relations(bad))

    def test_wm2_011_layout_solver(self):
        scene = world.solve_layout(self._spatial_scene())
        chair = [obj for obj in scene.objects if obj.id == "chair"][0]
        table = [obj for obj in scene.objects if obj.id == "table"][0]
        self.assertLess(chair.transform.position[0], table.transform.position[0])

    def test_wm2_012_constraint_layout(self):
        scene = world.apply_constraint_layout(self._spatial_scene())
        self.assertTrue(world.validate_layout(scene))

    def test_wm2_013_conflict_detection(self):
        scene = self._spatial_scene()
        scene = world.add_spatial_relation(scene, "rel-conflict", "chair", "table", "right_of")
        self.assertTrue(world.detect_conflicts(scene))

    def test_wm2_014_hierarchical_scene(self):
        scene = self._spatial_scene()
        self.assertTrue(world.validate_scene(scene))

    def test_wm2_015_hierarchical_world(self):
        w = world.add_scene(world.create_world("world-spatial"), self._spatial_scene())
        self.assertTrue(world.validate(w))

    def test_wm2_016_serialization(self):
        w = world.add_scene(world.create_world("world-spatial"), self._spatial_scene())
        payload = world.to_json(w)
        self.assertIn('"schema":"world-model-sdk/0.2"', payload)
        self.assertIn('"geometry":{', payload)
        self.assertIn('"hierarchy":{', payload)
        self.assertIn('"spatial_relations":[', payload)

    def test_wm2_017_query_api(self):
        scene = self._spatial_scene()
        self.assertEqual(world.geometry(scene, "chair").geometry_type, "Circle2D")
        self.assertEqual(world.parent(scene, "chair"), "room-object")
        self.assertEqual(world.children(scene, "room-object"), ["chair", "table"])

    def test_wm2_018_runtime_compatibility(self):
        w = world.add_scene(world.create_world("world-spatial"), self._spatial_scene())
        value = world.spatial_runtime_value(w)
        self.assertIsInstance(value, RuntimeValue)
        self.assertEqual(value.kind, "WorldModelSpatialValue")

    def test_wm2_019_deterministic_layout(self):
        self.assertEqual(
            world.solve_layout(self._spatial_scene()).to_dict(),
            world.solve_layout(self._spatial_scene()).to_dict(),
        )

    def test_wm2_020_deterministic_replay(self):
        w = world.add_scene(world.create_world("world-spatial"), world.solve_layout(self._spatial_scene()))
        self.assertEqual(world.to_json(w), world.to_json(w))


if __name__ == "__main__":
    unittest.main()
