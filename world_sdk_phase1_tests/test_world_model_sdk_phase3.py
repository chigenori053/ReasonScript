"""World Model SDK Phase 3 conformance tests - WM3-001 through WM3-020."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend.runtime_integration import RuntimeValue
from sdk import world


class WorldModelSDKPhase3Conformance(unittest.TestCase):
    def _scene(self, scene_id="room", objects=("Table",)):
        scene = world.create_scene(scene_id)
        for kind in objects:
            scene = world.add_object(scene, world.create_object(kind.lower(), kind=kind))
        return scene

    def test_wm3_001_template_creation(self):
        template = world.create_template("DiningRoom", required_objects=("Table", "Chair"))
        self.assertEqual(template.id, "DiningRoom")
        self.assertTrue(world.validate_template(template))

    def test_wm3_002_template_registration(self):
        template = world.create_template("Study", required_objects=("Desk",))
        registry = world.register_template(template, ())
        self.assertEqual([item.id for item in registry], ["Study"])

    def test_wm3_003_template_matching(self):
        template = world.match_template(self._scene(objects=("Table", "Chair")))
        self.assertEqual(template.id, "DiningRoom")

    def test_wm3_004_diningroom_reconstruction(self):
        result = world.reconstruct_scene(self._scene(objects=("Table",)))
        self.assertEqual(world.matched_template(result), "DiningRoom")
        self.assertIn("Chair", world.inferred_objects(result))

    def test_wm3_005_bedroom_reconstruction(self):
        result = world.reconstruct_scene(self._scene(objects=("Bed",)))
        self.assertEqual(world.matched_template(result), "Bedroom")
        self.assertTrue(world.validate_reconstruction(result))

    def test_wm3_006_office_reconstruction(self):
        result = world.reconstruct_scene(self._scene(objects=("Desk",)))
        self.assertEqual(world.matched_template(result), "Office")
        self.assertIn("Chair", world.inferred_objects(result))

    def test_wm3_007_object_inference(self):
        inferred = world.infer_objects(self._scene(objects=("Table",)))
        self.assertEqual([obj.kind for obj in inferred], ["Chair"])

    def test_wm3_008_relation_inference(self):
        scene = self._scene(objects=("Table", "Chair"))
        inferred = world.infer_relations(scene)
        self.assertEqual(inferred[0].relation_type, "near")

    def test_wm3_009_recoverable_completion(self):
        result = world.recover_structure(self._scene(objects=("Table",)))
        kinds = [obj.kind for obj in result.scene.objects]
        self.assertEqual(kinds, ["Table", "Chair"])

    def test_wm3_010_reconstruction_trace(self):
        result = world.reconstruct_scene(self._scene(objects=("Table",)))
        trace = world.reconstruction_trace(result)
        self.assertEqual(trace.template, "DiningRoom")

    def test_wm3_011_evidence_generation(self):
        result = world.reconstruct_scene(self._scene(objects=("Table",)))
        self.assertTrue(any("Chair inferred" in item for item in world.evidence(result)))

    def test_wm3_012_semantic_validation(self):
        result = world.reconstruct_scene(self._scene(objects=("Table",)))
        self.assertTrue(world.validate_semantic_consistency(result.scene, result.template))

    def test_wm3_013_reconstruction_validation(self):
        result = world.reconstruct_scene(self._scene(objects=("Table",)))
        self.assertTrue(world.validate_reconstruction(result))

    def test_wm3_014_world_reconstruction(self):
        w = world.add_scene(world.create_world("semantic-world"), self._scene(objects=("Table",)))
        result = world.reconstruct_world(w)
        self.assertEqual(world.inferred_objects(result), ("Chair",))

    def test_wm3_015_serialization(self):
        result = world.reconstruct_scene(self._scene(objects=("Table",)))
        payload = world.reconstruction_to_json(result)
        self.assertIn('"schema":"world-model-sdk/0.3"', payload)
        self.assertIn('"templates":[', payload)
        self.assertIn('"evidence":[', payload)

    def test_wm3_016_runtime_compatibility(self):
        w = world.add_scene(world.create_world("semantic-world"), self._scene(objects=("Table",)))
        value = world.semantic_runtime_value(w)
        self.assertIsInstance(value, RuntimeValue)
        self.assertEqual(value.kind, "WorldModelSemanticValue")

    def test_wm3_017_deterministic_reconstruction(self):
        r1 = world.reconstruct_scene(self._scene(objects=("Table",))).to_dict()
        r2 = world.reconstruct_scene(self._scene(objects=("Table",))).to_dict()
        self.assertEqual(r1, r2)

    def test_wm3_018_deterministic_replay(self):
        result = world.reconstruct_scene(self._scene(objects=("Table",)))
        self.assertEqual(world.reconstruction_to_json(result), world.reconstruction_to_json(result))

    def test_wm3_019_query_api(self):
        result = world.reconstruct_scene(self._scene(objects=("Table",)))
        self.assertEqual(world.matched_template(result), "DiningRoom")
        self.assertEqual(world.inferred_objects(result), ("Chair",))
        self.assertTrue(world.inferred_relations(result))

    def test_wm3_020_end_to_end_reconstruction(self):
        scene = self._scene(objects=("Table",))
        result = world.reconstruct_scene(scene)
        self.assertTrue(world.validate_reconstruction(result))
        self.assertEqual([obj.kind for obj in result.scene.objects], ["Table", "Chair"])
        self.assertEqual(world.matched_template(result), "DiningRoom")


if __name__ == "__main__":
    unittest.main()
