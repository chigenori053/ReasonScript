import json
import subprocess
import sys
import unittest

from conformance.framework import ROOT, canonical_reason_ir, load_json

sys.path.insert(0, str(ROOT / "dto" / "python"))
from reasonscript_dto import ReasonIR


class DtoConformanceTests(unittest.TestCase):
    def test_python_round_trip_preserves_all_core_fixtures(self):
        for path in sorted((ROOT / "fixtures" / "valid").glob("*.json")):
            source = load_json(path)
            restored = ReasonIR.from_dict(source).to_dict()
            self.assertEqual(canonical_reason_ir(restored), canonical_reason_ir(source))

    def test_python_preserves_metadata_and_uint64(self):
        source = load_json(ROOT / "fixtures" / "valid" / "tool_integration.json")
        source["metadata"]["extension"] = {"nested": [1, True, None]}
        self.assertEqual(
            ReasonIR.from_dict(source).to_dict()["metadata"]["extension"],
            source["metadata"]["extension"],
        )

    def test_rust_binding_round_trip_suite(self):
        completed = subprocess.run(
            ["cargo", "test", "--quiet", "--manifest-path", "dto/rust/Cargo.toml"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_typescript_binding_type_checks(self):
        completed = subprocess.run(
            [
                "tsc",
                "--noEmit",
                "--strict",
                "--target",
                "ES2022",
                "dto/typescript/index.ts",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_java_binding_compiles(self):
        completed = subprocess.run(
            [
                "javac",
                "-d",
                "/tmp/reasonscript-java-conformance",
                "dto/java/src/org/reasonscript/dto/CommonDtos.java",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
