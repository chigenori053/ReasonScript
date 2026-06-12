import unittest

from conformance.framework import ROOT, execute_reason_ir, load_json


class RuntimeConformanceTests(unittest.TestCase):
    def test_core_fixtures_have_deterministic_semantic_results(self):
        manifest = load_json(ROOT / "conformance" / "fixtures" / "manifest.json")
        for name, expected in manifest["core"].items():
            actual = execute_reason_ir(load_json(ROOT / "fixtures" / "valid" / name))
            for field, value in expected.items():
                self.assertEqual(actual[field], value, f"{name}: {field}")
            self.assertEqual(
                actual["state_delta_count"],
                len(actual["trace_delta_ids"]),
                name,
            )

    def test_repeated_execution_is_identical(self):
        for path in sorted((ROOT / "fixtures" / "valid").glob("*.json")):
            source = load_json(path)
            self.assertEqual(execute_reason_ir(source), execute_reason_ir(source), path.name)


if __name__ == "__main__":
    unittest.main()
