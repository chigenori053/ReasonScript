"""Tests validating official ReasonScript samples and documentation identity requirements (Issue #46)."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestOfficialSamplesAndDocumentation(unittest.TestCase):
    def test_official_samples_run_successfully(self) -> None:
        samples = [
            ("examples/01_hello_world.rsn", "Hello, World!"),
            ("examples/02_arithmetic.rsn", 42),
            ("examples/03_branching.rsn", "Pass"),
        ]
        for rel_path, expected_result in samples:
            path = REPO_ROOT / rel_path
            self.assertTrue(path.is_file(), f"Sample file not found: {rel_path}")

            # Check
            check_res = subprocess.run(
                ["./reason", "check", str(path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                check_res.returncode,
                0,
                f"check failed for {rel_path}:\n{check_res.stdout}\n{check_res.stderr}",
            )

            # Run with JSON
            run_res = subprocess.run(
                ["./reason", "run", str(path), "--json"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                run_res.returncode,
                0,
                f"run failed for {rel_path}:\n{run_res.stdout}\n{run_res.stderr}",
            )

            data = json.loads(run_res.stdout)
            actual_result = data.get("runtime_result", {}).get("result")
            self.assertEqual(
                actual_result,
                expected_result,
                f"Unexpected calculation result for {rel_path}: expected {expected_result}, got {actual_result}",
            )

    def test_documentation_contains_identity_and_disambiguation(self) -> None:
        doc_files = [
            "README.md",
            "docs/README.md",
            "docs/guides/quickstart.md",
            "docs/language-reference.md",
        ]
        for rel_path in doc_files:
            path = REPO_ROOT / rel_path
            self.assertTrue(path.is_file(), f"Doc file not found: {rel_path}")
            content = path.read_text(encoding="utf-8")

            self.assertIn(
                "independent",
                content.lower(),
                f"{rel_path} must state ReasonScript is an independent language",
            )
            self.assertIn(
                "not affiliated with",
                content.lower(),
                f"{rel_path} must state ReasonScript is not affiliated with ReScript/Reason",
            )
            self.assertIn(
                "rescript",
                content.lower(),
                f"{rel_path} must explicitly disambiguate from ReScript",
            )

    def test_no_rescript_artifacts_or_js_log(self) -> None:
        doc_files = [
            "README.md",
            "docs/README.md",
            "docs/guides/quickstart.md",
            "docs/language-reference.md",
        ]
        for rel_path in doc_files:
            content = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
            self.assertNotIn(
                "Js.log",
                content,
                f"{rel_path} must not recommend or use Js.log",
            )
            self.assertNotIn(
                "let%TEST",
                content,
                f"{rel_path} must not use ppx / rescript extension points",
            )

    def test_vscode_extension_identity_metadata(self) -> None:
        pkg_path = REPO_ROOT / "vscode-extension" / "package.json"
        data = json.loads(pkg_path.read_text(encoding="utf-8"))

        self.assertIn("independent reasoning-first", data.get("description", "").lower())
        keywords = data.get("keywords", [])
        self.assertIn("reasonscript", keywords)
        self.assertIn("reasoning", keywords)
        self.assertIn("ai", keywords)
