import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from frontend.conformance.framework import (
    ROOT,
    VALID_FIXTURES,
    canonical_ast,
    load_json,
)

sys.path.insert(0, str(ROOT / "frontend" / "dto" / "python"))
from reasonscript_ast_dto import from_dict, to_dict


class CrossLanguageAstTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name)
        completed = subprocess.run(
            [
                "tsc", "--target", "ES2022", "--module", "commonjs",
                "--moduleResolution", "node", "--outDir", str(cls.out),
                "frontend/conformance/adapters/typescript_adapter.ts",
            ],
            cwd=ROOT, text=True, capture_output=True,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_python_rust_and_typescript_round_trips_agree(self):
        for path in sorted(VALID_FIXTURES.glob("*.json")):
            source = load_json(path)
            outputs = [
                to_dict(from_dict(source)),
                json.loads(self._run([
                    "cargo", "run", "--quiet", "--manifest-path",
                    "frontend/dto/rust/Cargo.toml", "--bin", "roundtrip", "--",
                    str(path),
                ])),
                json.loads(self._run([
                    "node",
                    str(self.out / "conformance/adapters/typescript_adapter.js"),
                    str(path),
                ])),
            ]
            expected = canonical_ast(source)
            self.assertTrue(all(canonical_ast(item) == expected for item in outputs), path.name)

    @staticmethod
    def _run(command):
        completed = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr)
        return completed.stdout


if __name__ == "__main__":
    unittest.main()
