import shutil
import subprocess
import sys
import unittest

from frontend.conformance.framework import ROOT, VALID_FIXTURES, canonical_ast, load_json

sys.path.insert(0, str(ROOT / "frontend" / "dto" / "python"))
from reasonscript_ast_dto import from_dict, to_dict


class AstDtoConformanceTests(unittest.TestCase):
    def test_python_round_trip_and_immutability(self):
        for path in sorted(VALID_FIXTURES.glob("*.json")):
            source = load_json(path)
            dto = from_dict(source)
            self.assertEqual(canonical_ast(to_dict(dto)), canonical_ast(source))
            with self.assertRaises(Exception):
                dto.node_id = "changed"

    def test_rust_binding_round_trip(self):
        completed = subprocess.run(
            [
                "cargo", "run", "--quiet", "--manifest-path",
                "frontend/dto/rust/Cargo.toml", "--bin", "roundtrip", "--",
                str(VALID_FIXTURES / "basic_inference.json"),
            ],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            canonical_ast(__import__("json").loads(completed.stdout)),
            canonical_ast(load_json(VALID_FIXTURES / "basic_inference.json")),
        )

    def test_typescript_binding_type_checks(self):
        completed = subprocess.run(
            ["tsc", "--noEmit", "--strict", "--target", "ES2022",
             "frontend/dto/typescript/index.ts"],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_java_binding_compiles(self):
        completed = subprocess.run(
            ["javac", "-d", "/tmp/reasonscript-ast-java-conformance",
             "frontend/dto/java/src/org/reasonscript/ast/AstDtos.java"],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_go_binding_compiles_when_available(self):
        if shutil.which("go") is None:
            self.skipTest("Go toolchain is not installed")
        completed = subprocess.run(
            ["go", "test", "./..."], cwd=ROOT / "frontend" / "dto" / "go",
            text=True, capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
