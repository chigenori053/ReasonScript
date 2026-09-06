"""Comprehensive test suite for `reason migrate extensions` (Issue #50, [RS-DXLI-11]).

Verifies:
1. --check / --dry-run mode does not modify the filesystem.
2. Safe migration of legacy extensions (.re, .rei, .res, .resi, .reason, .rscript) to .rsn.
3. Updates references in reason.toml manifest.
4. Never overwrites existing .rsn files (SRC-0004 conflict rejection).
5. Detects and rejects many-to-one conflicts (multiple legacy files mapping to same .rsn).
6. Rejects case-insensitive target collisions.
7. Safely rejects symlinks without modifying target or link (SRC-0005).
8. Atomic execution with reverse rollback on partial failure.
9. Structured JSON output contract and proper exit codes (0, 1, 2).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from toolchain.migrate_extensions_cmd import (
    discover_legacy_files,
    plan_migrations,
    run as run_migrate,
)


class TestMigrateExtensions(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_check_mode_does_not_modify_filesystem(self) -> None:
        project_dir = self.tmp_dir / "project"
        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True)
        legacy_file = src_dir / "main.re"
        legacy_file.write_text("model Main {}", encoding="utf-8")
        manifest = project_dir / "reason.toml"
        manifest.write_text('[package]\nname = "test"\n\n[source]\nentry = "src/main.re"\n', encoding="utf-8")

        rc = run_migrate(["--check"], project_dir)
        self.assertEqual(rc, 0)

        # Ensure legacy file still exists and .rsn does NOT exist
        self.assertTrue(legacy_file.exists())
        self.assertFalse((src_dir / "main.rsn").exists())
        # Ensure manifest was not modified
        self.assertIn("src/main.re", manifest.read_text(encoding="utf-8"))

    def test_successful_migration_and_manifest_update(self) -> None:
        project_dir = self.tmp_dir / "project"
        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True)

        files = {
            "model.re": "model M {}",
            "types.res": "enum T { A }",
            "calc.reason": "calculation C { result = 1 }",
            "util.rscript": "pub fn Add() -> int { 1 }",
            "iface.rei": "interface I {}",
            "mod.resi": "interface M {}",
        }
        for name, content in files.items():
            (src_dir / name).write_text(content, encoding="utf-8")

        manifest = project_dir / "reason.toml"
        manifest.write_text('[package]\nname = "test"\n\n[source]\nentry = "src/model.re"\n', encoding="utf-8")

        rc = run_migrate([], project_dir)
        self.assertEqual(rc, 0)

        # All legacy files should be renamed to .rsn
        for name in files.keys():
            legacy_path = src_dir / name
            rsn_name = name.rsplit(".", 1)[0] + ".rsn"
            rsn_path = src_dir / rsn_name
            self.assertFalse(legacy_path.exists(), f"{legacy_path} should have been renamed")
            self.assertTrue(rsn_path.exists(), f"{rsn_path} should exist")

        # Manifest entry should be updated
        updated_manifest = manifest.read_text(encoding="utf-8")
        self.assertIn('entry = "src/model.rsn"', updated_manifest)
        self.assertNotIn("src/model.re", updated_manifest)

    def test_conflict_with_existing_rsn_rejects_and_never_overwrites(self) -> None:
        project_dir = self.tmp_dir / "project"
        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True)

        legacy_file = src_dir / "hello.re"
        legacy_file.write_text("legacy code", encoding="utf-8")
        existing_rsn = src_dir / "hello.rsn"
        existing_rsn.write_text("existing canonical code", encoding="utf-8")

        rc = run_migrate([], project_dir)
        self.assertEqual(rc, 1)

        # Both files should remain untouched
        self.assertTrue(legacy_file.exists())
        self.assertEqual(legacy_file.read_text(encoding="utf-8"), "legacy code")
        self.assertTrue(existing_rsn.exists())
        self.assertEqual(existing_rsn.read_text(encoding="utf-8"), "existing canonical code")

    def test_many_to_one_conflict_rejected(self) -> None:
        project_dir = self.tmp_dir / "project"
        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True)

        file1 = src_dir / "item.re"
        file2 = src_dir / "item.res"
        file1.write_text("v1", encoding="utf-8")
        file2.write_text("v2", encoding="utf-8")

        rc = run_migrate([], project_dir)
        self.assertEqual(rc, 1)

        self.assertTrue(file1.exists())
        self.assertTrue(file2.exists())
        self.assertFalse((src_dir / "item.rsn").exists())

    def test_case_insensitive_collision_rejected(self) -> None:
        project_dir = self.tmp_dir / "project"
        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True)

        # Two files that differ only in casing in destination
        file1 = src_dir / "User.re"
        file2 = src_dir / "user.res"
        file1.write_text("u1", encoding="utf-8")
        file2.write_text("u2", encoding="utf-8")

        items, conflicts = plan_migrations(project_dir, [file1, file2])
        self.assertTrue(len(conflicts) > 0)
        self.assertEqual(conflicts[0].diagnostic_code, "SRC-0004")

    def test_symlink_rejection(self) -> None:
        project_dir = self.tmp_dir / "project"
        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True)

        target_file = self.tmp_dir / "external.re"
        target_file.write_text("external", encoding="utf-8")
        symlink_file = src_dir / "link.re"
        try:
            os.symlink(target_file, symlink_file)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not supported in this test environment")

        rc = run_migrate([], project_dir)
        self.assertEqual(rc, 1)
        self.assertTrue(symlink_file.is_symlink())
        self.assertTrue(target_file.exists())

    def test_rollback_on_partial_failure(self) -> None:
        project_dir = self.tmp_dir / "project"
        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True)

        file1 = src_dir / "a_first.re"
        file2 = src_dir / "b_second.re"
        file1.write_text("content 1", encoding="utf-8")
        file2.write_text("content 2", encoding="utf-8")

        manifest = project_dir / "reason.toml"
        manifest.write_text('[source]\nentry = "src/a_first.re"\n', encoding="utf-8")

        original_rename = Path.rename
        call_count = 0

        def failing_rename(self_path: Path, target: Path | str) -> Path:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise PermissionError("Simulated permission error on second rename")
            return original_rename(self_path, target)

        with patch.object(Path, "rename", side_effect=failing_rename):
            rc = run_migrate([], project_dir)
            self.assertEqual(rc, 2)

        # First file must have been rolled back to a_first.re
        self.assertTrue(file1.exists(), "a_first.re should be rolled back to original name")
        self.assertFalse((src_dir / "a_first.rsn").exists())
        self.assertTrue(file2.exists())
        # Manifest should be preserved as-is
        self.assertIn("src/a_first.re", manifest.read_text(encoding="utf-8"))

    def test_json_output_mode(self) -> None:
        project_dir = self.tmp_dir / "project"
        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "mod.re").write_text("model Mod {}", encoding="utf-8")

        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            rc = run_migrate(["--check", "--json"], project_dir)
        self.assertEqual(rc, 0)

        output = buffer.getvalue()
        report = json.loads(output)
        self.assertEqual(report["command"], "migrate extensions")
        self.assertEqual(report["status"], "success")
        self.assertTrue(report["check_mode"])
        self.assertEqual(len(report["planned_migrations"]), 1)
        self.assertEqual(report["planned_migrations"][0]["from"], "src/mod.re")
        self.assertEqual(report["planned_migrations"][0]["to"], "src/mod.rsn")

    def test_cli_dispatch_via_main(self) -> None:
        import sys
        from toolchain.__main__ import main

        project_dir = self.tmp_dir / "project"
        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "app.re").write_text("model App {}", encoding="utf-8")

        # Test CLI help
        with patch.object(sys, "argv", ["reason", "migrate", "extensions", "--help"]):
            self.assertEqual(main(), 0)

        # Test CLI check mode with explicit path
        with patch.object(sys, "argv", ["reason", "migrate", "extensions", "--check", str(project_dir)]):
            self.assertEqual(main(), 0)
        self.assertTrue((src_dir / "app.re").exists())

        # Test CLI execute mode with explicit path
        with patch.object(sys, "argv", ["reason", "migrate", "extensions", str(project_dir)]):
            self.assertEqual(main(), 0)
        self.assertFalse((src_dir / "app.re").exists())
        self.assertTrue((src_dir / "app.rsn").exists())


if __name__ == "__main__":
    unittest.main()
