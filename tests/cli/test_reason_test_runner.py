from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from toolchain.runner_cmd import run

class ReasonTestRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "reason.toml").write_text("""[package]
name = "test_pkg"
version = "0.1.0"
type = "library"
""", encoding="utf-8")
        (self.root / "src").mkdir()
        (self.root / "tests").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_passing_test_with_assertions(self):
        (self.root / "tests" / "test_math.rsn").write_text("""module TestMath {
  calculation TestAdd {
    let x: int = 10 + 20
    assert_eq(x, 30)
    assert(x > 0)
    result = true
  }
}
""", encoding="utf-8")
        rc = run(self.root)
        self.assertEqual(rc, 0)

    def test_failing_test_assertion_error(self):
        (self.root / "tests" / "test_fail.rsn").write_text("""module TestFail {
  calculation TestWrong {
    assert_eq(10, 999)
    result = true
  }
}
""", encoding="utf-8")
        rc = run(self.root)
        self.assertEqual(rc, 3)

    def test_compile_only_skips_assertion_failure(self):
        (self.root / "tests" / "test_fail.rsn").write_text("""module TestFail {
  calculation TestWrong {
    assert_eq(10, 999)
    result = true
  }
}
""", encoding="utf-8")
        rc = run(self.root, compile_only=True)
        self.assertEqual(rc, 0)

    def test_junit_output(self):
        (self.root / "tests" / "test_ok.rsn").write_text("""module TestOk {
  calculation TestPass {
    assert(true)
    result = true
  }
}
""", encoding="utf-8")
        junit_file = self.root / "junit.xml"
        rc = run(self.root, junit_path=junit_file)
        self.assertEqual(rc, 0)
        self.assertTrue(junit_file.exists())
        self.assertIn("test_ok", junit_file.read_text(encoding="utf-8"))
