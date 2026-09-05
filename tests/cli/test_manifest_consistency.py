"""E2E regression tests for reason init and Manifest consistency (Issue #31, #33-#35)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestManifestConsistency(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)
        self.cli = [sys.executable, str(REPO_ROOT / "reason")]

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _run_cli(self, args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        return subprocess.run(
            [*self.cli, *args],
            cwd=cwd or self.tmp_path,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_init_to_build_and_run_zero_warnings(self):
        """T-001 & T-002: reason init creates standard structure and reason build passes with zero manifest warnings."""
        proj_name = "manifest-consistency-test"
        res_init = self._run_cli(["init", proj_name])
        self.assertEqual(res_init.returncode, 0, res_init.stderr)

        proj_path = self.tmp_path / proj_name
        self.assertTrue((proj_path / ".gitignore").is_file())
        self.assertTrue((proj_path / "artifacts" / ".gitkeep").is_file())
        self.assertTrue((proj_path / "README.md").is_file())
        self.assertTrue((proj_path / "reason.toml").is_file())
        self.assertTrue((proj_path / "src" / "main.rsn").is_file())
        self.assertTrue((proj_path / "tests" / "sample_test.rsn").is_file())

        # reason build
        res_build = self._run_cli(["build"], cwd=proj_path)
        self.assertEqual(res_build.returncode, 0, res_build.stderr)
        self.assertIn("Build succeeded. 1 file(s) compiled.", res_build.stdout)
        self.assertNotIn("Unknown sections", res_build.stderr)
        self.assertNotIn("UserWarning", res_build.stderr)

        # reason run
        res_run = self._run_cli(["run"], cwd=proj_path)
        self.assertEqual(res_run.returncode, 0, res_run.stderr)

    def test_unknown_section_emits_warning(self):
        """T-004: Truly unknown sections are still reported with a UserWarning."""
        proj_name = "unknown-section-test"
        self._run_cli(["init", proj_name])
        proj_path = self.tmp_path / proj_name

        toml_path = proj_path / "reason.toml"
        toml_content = toml_path.read_text(encoding="utf-8")
        toml_path.write_text(toml_content + "\n[unexpected_section]\nfoo = \"bar\"\n", encoding="utf-8")

        res_build = self._run_cli(["build"], cwd=proj_path)
        self.assertEqual(res_build.returncode, 0)
        self.assertIn("Unknown sections in reason.toml: unexpected_section", res_build.stderr)

    def test_unknown_key_emits_warning(self):
        """Known sections with unknown keys report deterministic UserWarnings."""
        proj_name = "unknown-key-test"
        self._run_cli(["init", proj_name])
        proj_path = self.tmp_path / proj_name

        toml_path = proj_path / "reason.toml"
        toml_content = toml_path.read_text(encoding="utf-8")
        toml_path.write_text(toml_content.replace("[package]\n", "[package]\nunknown_field = 123\n"), encoding="utf-8")

        res_build = self._run_cli(["build"], cwd=proj_path)
        self.assertEqual(res_build.returncode, 0, f"stdout: {res_build.stdout}, stderr: {res_build.stderr}")
        self.assertIn("Unknown keys in reason.toml [package]: unknown_field", res_build.stderr)

    def test_path_escaping_project_root_rejected(self):
        """Escaping project root in source.entry or artifacts.directory is rejected."""
        proj_name = "escape-test"
        self._run_cli(["init", proj_name])
        proj_path = self.tmp_path / proj_name

        toml_path = proj_path / "reason.toml"
        orig_content = toml_path.read_text(encoding="utf-8")

        # Escaped source.entry
        toml_path.write_text(orig_content.replace('entry = "src/main.rsn"', 'entry = "../outside.rsn"'), encoding="utf-8")
        res_build = self._run_cli(["build"], cwd=proj_path)
        self.assertNotEqual(res_build.returncode, 0)
        self.assertIn("source.entry cannot escape project root", res_build.stdout)

        # Escaped artifacts.directory
        toml_path.write_text(orig_content.replace('directory = "artifacts"', 'directory = "../outside"'), encoding="utf-8")
        res_build = self._run_cli(["build"], cwd=proj_path)
        self.assertNotEqual(res_build.returncode, 0)
        self.assertIn("artifacts.directory cannot escape project root", res_build.stdout)

    def test_custom_source_entry_builds(self):
        """Custom source.entry builds correctly as the entry point."""
        proj_name = "custom-entry-test"
        self._run_cli(["init", proj_name])
        proj_path = self.tmp_path / proj_name

        # Rename main.rsn to application.rsn
        (proj_path / "src" / "main.rsn").rename(proj_path / "src" / "application.rsn")

        toml_path = proj_path / "reason.toml"
        content = toml_path.read_text(encoding="utf-8")
        toml_path.write_text(content.replace('entry = "src/main.rsn"', 'entry = "src/application.rsn"'), encoding="utf-8")

        res_build = self._run_cli(["build"], cwd=proj_path)
        self.assertEqual(res_build.returncode, 0, res_build.stderr)
        self.assertIn("Build succeeded. 1 file(s) compiled.", res_build.stdout)

    def test_custom_artifacts_directory(self):
        """Custom artifacts.directory is respected by reason artifacts."""
        proj_name = "custom-artifacts-test"
        self._run_cli(["init", proj_name])
        proj_path = self.tmp_path / proj_name

        toml_path = proj_path / "reason.toml"
        content = toml_path.read_text(encoding="utf-8")
        toml_path.write_text(content.replace('directory = "artifacts"', 'directory = "build-artifacts"'), encoding="utf-8")

        res_art = self._run_cli(["artifacts", "src/main.rsn"], cwd=proj_path)
        self.assertEqual(res_art.returncode, 0, res_art.stderr)
        self.assertTrue((proj_path / "build-artifacts" / "artifact_manifest.json").is_file())

    def test_deterministic_diagnostic_ordering(self):
        """Multiple unknown sections and keys are warned in deterministic alphabetical order."""
        proj_name = "determinism-test"
        self._run_cli(["init", proj_name])
        proj_path = self.tmp_path / proj_name

        toml_path = proj_path / "reason.toml"
        content = toml_path.read_text(encoding="utf-8")
        modified = content.replace("[package]\n", "[package]\nz_extra = 1\na_extra = 2\n")
        modified += "\n[zebra]\nk = 1\n[alpha]\nk = 1\n"
        toml_path.write_text(modified, encoding="utf-8")

        outputs = []
        for _ in range(3):
            res = self._run_cli(["build"], cwd=proj_path)
            outputs.append(res.stderr)

        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])
        self.assertIn("Unknown sections in reason.toml: alpha, zebra", outputs[0])
        self.assertIn("Unknown keys in reason.toml [package]: a_extra, z_extra", outputs[0])


if __name__ == "__main__":
    unittest.main()
