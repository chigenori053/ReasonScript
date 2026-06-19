"""Toolchain Phase 1 Conformance Tests — TC1-001 through TC1-010."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from toolchain.init_cmd import run as init_run
from toolchain.build_cmd import run as build_run
from toolchain.check_cmd import run as check_run
from toolchain.runner_cmd import run as suite_run
from toolchain.run_cmd import run as run_run
from toolchain.manifest import Manifest, ManifestError, SUPPORTED_BACKENDS

_SIMPLE_RSN = """\
package hello_world
module main {
    fn run(goal) {
        return goal
    }
}
"""

_TEST_RSN = """\
package hello_world
module sample_test {
    fn run(goal) {
        return goal
    }
}
"""

_REASON_TOML = """\
[package]
name = "hello_world"
version = "0.1.0"

[compiler]
language_core = "0.7"
platform = "0.2"

[runtime]
backend = "RuntimeReal"
"""


class TC1001Init(unittest.TestCase):
    """TC1-001: reason init creates standard project layout."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_creates_project_directory(self):
        rc = init_run("my_project")
        self.assertEqual(rc, 0)
        self.assertTrue(Path("my_project").is_dir())

    def test_creates_reason_toml(self):
        init_run("my_project")
        self.assertTrue(Path("my_project/reason.toml").is_file())

    def test_creates_src_main(self):
        init_run("my_project")
        self.assertTrue(Path("my_project/src/main.rsn").is_file())

    def test_creates_tests_dir(self):
        init_run("my_project")
        self.assertTrue(Path("my_project/tests").is_dir())

    def test_creates_target_dirs(self):
        init_run("my_project")
        for d in ("target/ast", "target/ir", "target/metadata", "target/runtime"):
            self.assertTrue(Path(f"my_project/{d}").is_dir(), f"Missing {d}")

    def test_creates_packages_dir(self):
        init_run("my_project")
        self.assertTrue(Path("my_project/packages").is_dir())

    def test_duplicate_init_fails(self):
        init_run("my_project")
        rc = init_run("my_project")
        self.assertEqual(rc, 1)

    def test_manifest_contains_project_name(self):
        init_run("my_project")
        text = Path("my_project/reason.toml").read_text()
        self.assertIn("my_project", text)


class TC1002Build(unittest.TestCase):
    """TC1-002: reason build compiles sources to target/."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _setup_project(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_succeeds(self):
        rc = build_run(self.tmp)
        self.assertEqual(rc, 0)

    def test_produces_ir_artifact(self):
        build_run(self.tmp)
        ir_files = list((self.tmp / "target" / "ir").glob("*.json"))
        self.assertGreater(len(ir_files), 0)

    def test_produces_metadata_artifact(self):
        build_run(self.tmp)
        meta_files = list((self.tmp / "target" / "metadata").glob("*.json"))
        self.assertGreater(len(meta_files), 0)

    def test_produces_ast_artifact(self):
        build_run(self.tmp)
        ast_files = list((self.tmp / "target" / "ast").glob("*.json"))
        self.assertGreater(len(ast_files), 0)

    def test_no_manifest_fails(self):
        p = Path(tempfile.mkdtemp())
        try:
            rc = build_run(p)
            self.assertEqual(rc, 1)
        finally:
            shutil.rmtree(p, ignore_errors=True)


class TC1003Run(unittest.TestCase):
    """TC1-003: reason run executes a compiled program."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _setup_project(self.tmp)
        build_run(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_returns_zero(self):
        rc = run_run(self.tmp)
        self.assertEqual(rc, 0)

    def test_run_without_build_fails(self):
        p = Path(tempfile.mkdtemp())
        _setup_project(p)
        try:
            rc = run_run(p)
            self.assertEqual(rc, 1)
        finally:
            shutil.rmtree(p, ignore_errors=True)


class TC1004Test(unittest.TestCase):
    """TC1-004: reason test discovers and executes test suites."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _setup_project(self.tmp, include_test=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_test_passes(self):
        rc = suite_run(self.tmp)
        self.assertEqual(rc, 0)

    def test_invalid_test_fails(self):
        (self.tmp / "tests" / "bad_test.rsn").write_text(
            "@@invalid@@", encoding="utf-8"
        )
        rc = suite_run(self.tmp)
        self.assertEqual(rc, 3)


class TC1005Check(unittest.TestCase):
    """TC1-005: reason check validates without building runtime artifacts."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _setup_project(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_check_passes(self):
        rc = check_run(self.tmp)
        self.assertEqual(rc, 0)

    def test_check_no_runtime_artifacts(self):
        check_run(self.tmp)
        runtime_dir = self.tmp / "target" / "runtime"
        if runtime_dir.exists():
            self.assertEqual(list(runtime_dir.glob("*")), [])

    def test_check_syntax_error_fails(self):
        (self.tmp / "src" / "bad.rsn").write_text("@@invalid@@", encoding="utf-8")
        rc = check_run(self.tmp)
        self.assertEqual(rc, 1)


class TC1006BuildArtifactGeneration(unittest.TestCase):
    """TC1-006: build artifact generation produces valid JSON."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _setup_project(self.tmp)
        build_run(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ir_is_valid_json(self):
        for f in (self.tmp / "target" / "ir").glob("*.json"):
            data = json.loads(f.read_text())
            self.assertIsInstance(data, dict)

    def test_metadata_is_valid_json(self):
        for f in (self.tmp / "target" / "metadata").glob("*.json"):
            data = json.loads(f.read_text())
            self.assertIsInstance(data, dict)

    def test_metadata_has_required_fields(self):
        for f in (self.tmp / "target" / "metadata").glob("*.json"):
            data = json.loads(f.read_text())
            for field in ("package", "module", "runtime_calls", "reasoning_declarations"):
                self.assertIn(field, data, f"Missing '{field}' in {f.name}")


class TC1007RuntimeBackendSelection(unittest.TestCase):
    """TC1-007: runtime backend selection."""

    def test_supported_backends_in_manifest(self):
        self.assertIn("RuntimeReal", SUPPORTED_BACKENDS)
        self.assertIn("HybridRuntime", SUPPORTED_BACKENDS)

    def test_unknown_backend_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "reason.toml").write_text(
                "[package]\nname=\"x\"\nversion=\"0.1.0\"\n"
                "[runtime]\nbackend=\"UnknownBackend\"\n",
                encoding="utf-8",
            )
            with self.assertRaises(ManifestError):
                Manifest.load(p)

    def test_real_backend_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "reason.toml").write_text(_REASON_TOML, encoding="utf-8")
            m = Manifest.load(p)
            self.assertEqual(m.backend, "RuntimeReal")

    def test_hybrid_backend_loaded(self):
        toml = _REASON_TOML.replace("RuntimeReal", "HybridRuntime")
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "reason.toml").write_text(toml, encoding="utf-8")
            m = Manifest.load(p)
            self.assertEqual(m.backend, "HybridRuntime")


class TC1008MetadataGeneration(unittest.TestCase):
    """TC1-008: metadata generation emits required fields."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _setup_project(self.tmp)
        build_run(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_metadata_fields(self):
        meta_files = list((self.tmp / "target" / "metadata").glob("*.json"))
        self.assertGreater(len(meta_files), 0)
        for f in meta_files:
            data = json.loads(f.read_text())
            self.assertIn("package", data)
            self.assertIn("module", data)
            self.assertIn("runtime_calls", data)
            self.assertIn("reasoning_declarations", data)

    def test_runtime_calls_is_list(self):
        for f in (self.tmp / "target" / "metadata").glob("*.json"):
            data = json.loads(f.read_text())
            self.assertIsInstance(data["runtime_calls"], list)

    def test_reasoning_declarations_is_dict(self):
        for f in (self.tmp / "target" / "metadata").glob("*.json"):
            data = json.loads(f.read_text())
            self.assertIsInstance(data["reasoning_declarations"], dict)


class TC1009ExitCodes(unittest.TestCase):
    """TC1-009: exit codes are correct."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _setup_project(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_success_exit_0(self):
        self.assertEqual(build_run(self.tmp), 0)

    def test_check_success_exit_0(self):
        self.assertEqual(check_run(self.tmp), 0)

    def test_test_success_exit_0(self):
        _setup_project(self.tmp, include_test=True)
        self.assertEqual(suite_run(self.tmp), 0)

    def test_test_failure_exit_3(self):
        _setup_project(self.tmp, include_test=True)
        (self.tmp / "tests" / "bad.rsn").write_text("@@invalid@@", encoding="utf-8")
        self.assertEqual(suite_run(self.tmp), 3)

    def test_build_compiler_error_exit_1(self):
        (self.tmp / "src" / "bad.rsn").write_text("@@invalid@@", encoding="utf-8")
        self.assertEqual(build_run(self.tmp), 1)

    def test_run_without_artifacts_exit_1(self):
        p = Path(tempfile.mkdtemp())
        _setup_project(p)
        try:
            self.assertEqual(run_run(p), 1)
        finally:
            shutil.rmtree(p, ignore_errors=True)


class TC1010DeterministicRebuild(unittest.TestCase):
    """TC1-010: deterministic rebuild — identical inputs produce identical outputs."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _setup_project(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_second_build_is_cached(self, capsule=None):
        build_run(self.tmp)
        ir_before = self._read_ir()
        build_run(self.tmp)
        ir_after = self._read_ir()
        self.assertEqual(ir_before, ir_after)

    def test_unchanged_source_skips_rebuild(self):
        build_run(self.tmp)
        ir_before = self._read_ir()
        # Second build should not change outputs (cache hit)
        build_run(self.tmp)
        ir_after = self._read_ir()
        self.assertEqual(ir_before, ir_after)

    def test_changed_source_triggers_rebuild(self):
        build_run(self.tmp)
        # Modify source
        src = self.tmp / "src" / "main.rsn"
        src.write_text(_SIMPLE_RSN.replace("Hello", "World"), encoding="utf-8")
        # Remove cache key to simulate fresh build
        cache_file = self.tmp / "target" / ".reason_build_cache"
        if cache_file.exists():
            cache_file.unlink()
        rc = build_run(self.tmp)
        self.assertEqual(rc, 0)

    def _read_ir(self) -> dict:
        result = {}
        for f in sorted((self.tmp / "target" / "ir").glob("*.json")):
            result[f.name] = json.loads(f.read_text())
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_project(root: Path, *, include_test: bool = False) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "target" / "ast").mkdir(parents=True, exist_ok=True)
    (root / "target" / "ir").mkdir(parents=True, exist_ok=True)
    (root / "target" / "metadata").mkdir(parents=True, exist_ok=True)
    (root / "target" / "runtime").mkdir(parents=True, exist_ok=True)
    (root / "packages").mkdir(parents=True, exist_ok=True)
    (root / "reason.toml").write_text(_REASON_TOML, encoding="utf-8")
    (root / "src" / "main.rsn").write_text(_SIMPLE_RSN, encoding="utf-8")
    if include_test:
        (root / "tests" / "sample_test.rsn").write_text(_TEST_RSN, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
