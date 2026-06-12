import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from conformance.framework import ROOT, canonical_reason_ir, load_json


class PlatformConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name)
        ts = subprocess.run(
            [
                "tsc",
                "--target",
                "ES2022",
                "--module",
                "commonjs",
                "--moduleResolution",
                "node",
                "--outDir",
                str(cls.out),
                "conformance/adapters/typescript_adapter.ts",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if ts.returncode != 0:
            raise AssertionError(ts.stdout + ts.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_rust_python_and_typescript_agree_on_core_fixtures(self):
        for path in sorted((ROOT / "fixtures" / "valid").glob("*.json")):
            outputs = [
                self._run(
                    [sys.executable, "conformance/adapters/python_adapter.py", str(path)]
                ),
                self._run(
                    [
                        "cargo",
                        "run",
                        "--quiet",
                        "--manifest-path",
                        "dto/rust/Cargo.toml",
                        "--bin",
                        "conformance_adapter",
                        "--",
                        str(path),
                    ]
                ),
                self._run(["node", str(self.out / "conformance/adapters/typescript_adapter.js"), str(path)]),
            ]
            canonical = [canonical_reason_ir(json.loads(output)) for output in outputs]
            self.assertEqual(canonical[1:], canonical[:-1], path.name)

    def test_available_go_adapter_agrees_with_python(self):
        if shutil.which("go") is None:
            self.skipTest("Go toolchain is not installed")
        path = ROOT / "fixtures" / "valid" / "dog_to_animal.json"
        python = json.loads(
            self._run([sys.executable, "conformance/adapters/python_adapter.py", str(path)])
        )
        go = json.loads(
            self._run(["go", "run", "./cmd/conformance_adapter", str(path)], cwd=ROOT / "dto/go")
        )
        self.assertEqual(canonical_reason_ir(go), canonical_reason_ir(python))

    @staticmethod
    def _run(command, cwd=ROOT):
        completed = subprocess.run(
            command, cwd=cwd, text=True, capture_output=True
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr)
        return completed.stdout


if __name__ == "__main__":
    unittest.main()
