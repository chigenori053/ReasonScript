import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class BindingShapeTests(unittest.TestCase):
    def test_all_schemas_are_json_documents(self):
        for path in sorted((ROOT / "schemas").glob("*.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
            )
            self.assertIn("$id", schema)

    def test_every_binding_defines_level_four_dtos(self):
        files = {
            "rust": ROOT / "dto/rust/src/lib.rs",
            "python": ROOT / "dto/python/reasonscript_dto/models.py",
            "typescript": ROOT / "dto/typescript/index.ts",
            "go": ROOT / "dto/go/dto.go",
            "java": ROOT / "dto/java/src/org/reasonscript/dto/CommonDtos.java",
        }
        required = (
            "ReasonIR",
            "ExecutionPlan",
            "StateDelta",
            "InferenceResult",
            "Trace",
            "TransactionRecord",
        )
        for language, path in files.items():
            source = path.read_text(encoding="utf-8")
            for dto in required:
                self.assertIn(dto, source, f"{language} is missing {dto}")

    def test_prepared_delta_is_not_exported_by_sdk_bindings(self):
        for path in (
            ROOT / "dto/rust/src/lib.rs",
            ROOT / "dto/python/reasonscript_dto/models.py",
            ROOT / "dto/typescript/index.ts",
            ROOT / "dto/go/dto.go",
            ROOT / "dto/java/src/org/reasonscript/dto/CommonDtos.java",
        ):
            self.assertNotIn("PreparedDelta", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
