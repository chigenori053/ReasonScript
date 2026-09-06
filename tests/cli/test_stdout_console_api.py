"""Tests validating ReasonScript native standard output APIs and rejection of Js.* (Issue #47)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from frontend.compiler_frontend import CompilerFrontend, FrontendRequest
from toolchain.diagnostics import DEFAULT_REGISTRY

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestStdoutConsoleApi(unittest.TestCase):
    def test_registry_contains_nam_2004(self) -> None:
        defn = DEFAULT_REGISTRY.get("NAM-2004")
        self.assertIsNotNone(defn)
        self.assertEqual(defn.code, "NAM-2004")
        self.assertEqual(defn.title, "Unsupported JavaScript API")
        self.assertIn("Console.log", defn.default_help)

    def test_rejection_of_js_log_with_nam_2004_and_fixes(self) -> None:
        source = """
model TestJsLog {
    calculation Main {
        Js.log("hello")
        result = 0
    }
}
"""
        req = FrontendRequest(source=source, filename="test_js.rsn")
        res = CompilerFrontend.analyze(req)
        self.assertFalse(res.ok)
        self.assertTrue(any(d.code == "NAM-2004" for d in res.diagnostics))
        diag = next(d for d in res.diagnostics if d.code == "NAM-2004")
        self.assertEqual(diag.title, "Unsupported JavaScript API")
        self.assertIn("Console.log", diag.help)
        self.assertTrue(len(diag.fixes) >= 2)
        fix_replacements = [f.replacement for f in diag.fixes]
        self.assertIn("Console.log", fix_replacements)
        self.assertIn("print", fix_replacements)

    def test_print_api_outputs_to_stdout(self) -> None:
        code = """
model TestPrint {
    calculation Main {
        print("Hello, ReasonScript")
        result = 1
    }
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test_print.rsn"
            file_path.write_text(code, encoding="utf-8")

            # Check
            check_res = subprocess.run(
                ["./reason", "check", str(file_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(check_res.returncode, 0, check_res.stderr)

            # Run (Rust production path)
            run_res = subprocess.run(
                ["./reason", "run", str(file_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(run_res.returncode, 0, run_res.stderr)
            self.assertIn("Hello, ReasonScript", run_res.stdout)

    def test_console_levels_and_streams(self) -> None:
        code = """
model TestConsoleLevels {
    calculation Main {
        Console.log("log_message", 100)
        Console.info("info_message", true)
        Console.warn("warn_message", 3.14)
        Console.error("error_message", null)
        result = 42
    }
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test_console.rsn"
            file_path.write_text(code, encoding="utf-8")

            # Check
            check_res = subprocess.run(
                ["./reason", "check", str(file_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(check_res.returncode, 0, check_res.stderr)

            # Run
            run_res = subprocess.run(
                ["./reason", "run", str(file_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(run_res.returncode, 0, run_res.stderr)
            # log and info to stdout
            self.assertIn("log_message 100", run_res.stdout)
            self.assertIn("info_message true", run_res.stdout)
            # warn and error to stderr
            self.assertIn("warn_message 3.14", run_res.stderr)
            self.assertIn("error_message null", run_res.stderr)

            # Run with --json captures console_output deterministically
            json_res = subprocess.run(
                ["./reason", "run", str(file_path), "--json"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json_res.returncode, 0, json_res.stderr)
            data = json.loads(json_res.stdout)
            console_output = data.get("console_output", [])
            self.assertEqual(len(console_output), 4)
            self.assertEqual(console_output[0]["stream"], "stdout")
            self.assertEqual(console_output[0]["level"], "log")
            self.assertEqual(console_output[0]["message"], "log_message 100")
            self.assertEqual(console_output[1]["stream"], "stdout")
            self.assertEqual(console_output[1]["level"], "info")
            self.assertEqual(console_output[1]["message"], "info_message true")
            self.assertEqual(console_output[2]["stream"], "stderr")
            self.assertEqual(console_output[2]["level"], "warn")
            self.assertEqual(console_output[2]["message"], "warn_message 3.14")
            self.assertEqual(console_output[3]["stream"], "stderr")
            self.assertEqual(console_output[3]["level"], "error")
            self.assertEqual(console_output[3]["message"], "error_message null")

    def test_deterministic_formatting(self) -> None:
        code = """
model TestFormatting {
    calculation Main {
        Console.log([1, 2, 3])
        Console.log(true, false, null)
        result = 0
    }
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test_formatting.rsn"
            file_path.write_text(code, encoding="utf-8")

            run_res = subprocess.run(
                ["./reason", "run", str(file_path), "--json"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(run_res.returncode, 0, run_res.stderr)
            data = json.loads(run_res.stdout)
            messages = [e["message"] for e in data.get("console_output", [])]
            self.assertEqual(messages, ["[1, 2, 3]", "true false null"])


if __name__ == "__main__":
    unittest.main()
