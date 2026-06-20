"""Toolchain Phase 2 Conformance Tests - TC2-001 through TC2-020."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from frontend.ide import ReasonScriptIde
from frontend.lsp import ReasonScriptLanguageServer
from frontend.runtime_integration import PLATFORM_DIAGNOSTIC_SCHEMA
from toolchain.build_cmd import run as build_run
from toolchain.check_cmd import run as check_run
from toolchain.manifest import Manifest
from toolchain.run_cmd import run as run_run
from toolchain.runner_cmd import run as suite_run
from toolchain.workspace import (
    PACKAGE_GRAPH_SCHEMA,
    DependencyCycleError,
    InvalidVersionError,
    MissingPackageError,
    PackageGraphService,
    UnknownPackageError,
    WorkspaceManifest,
    diagnostic_from_workspace_error,
)


MAIN = """\
package {name}
module main {{
    fn run(goal) {{
        return goal
    }}
}}
"""

TEST = """\
package {name}
module sample_test {{
    fn run(goal) {{
        return goal
    }}
}}
"""


class ToolchainPhase2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _workspace(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_tc2_001_workspace_discovery(self):
        workspace = PackageGraphService().discover(self.tmp / "app" / "src")

        self.assertTrue(workspace.is_workspace)
        self.assertEqual(workspace.root, self.tmp.resolve())

    def test_tc2_002_workspace_manifest_parse(self):
        manifest = WorkspaceManifest.load(self.tmp)

        self.assertEqual(manifest.members, ("core", "world", "app"))
        self.assertEqual(manifest.default_package, "app")

    def test_tc2_003_package_manifest_parse(self):
        manifest = Manifest.load(self.tmp / "app")

        self.assertEqual(manifest.name, "app")
        self.assertEqual(manifest.dependencies["world"], {"path": "../world"})

    def test_tc2_004_local_dependency_resolution(self):
        graph = PackageGraphService().discover(self.tmp).graph
        edge = next(edge for edge in graph.dependencies if edge.package == "app")

        self.assertEqual(edge.dependency, "world")
        self.assertEqual(edge.kind, "path")

    def test_tc2_005_dependency_graph_creation(self):
        graph = PackageGraphService().discover(self.tmp).graph.to_dict()

        self.assertEqual(graph["schema"], PACKAGE_GRAPH_SCHEMA)
        self.assertEqual([package["name"] for package in graph["packages"]], ["app", "core", "world"])

    def test_tc2_006_topological_sort(self):
        graph = PackageGraphService().discover(self.tmp).graph

        self.assertEqual(graph.build_order, ("core", "world", "app"))

    def test_tc2_007_dependency_cycle_detection(self):
        _write_manifest(self.tmp / "core", "core", deps='app = { path = "../app" }\n')

        with self.assertRaises(DependencyCycleError):
            PackageGraphService().discover(self.tmp)

    def test_tc2_008_missing_package_detection(self):
        shutil.rmtree(self.tmp / "world")

        with self.assertRaises(MissingPackageError):
            PackageGraphService().discover(self.tmp)

    def test_tc2_009_unknown_dependency_detection(self):
        _write_manifest(self.tmp / "app", "app", deps='ghost = "0.1.0"\n')

        with self.assertRaises(UnknownPackageError):
            PackageGraphService().discover(self.tmp)

    def test_tc2_010_exact_version_validation(self):
        _write_manifest(self.tmp / "app", "app", deps='world = ">=0.1.0"\n')

        with self.assertRaises(InvalidVersionError):
            PackageGraphService().discover(self.tmp)

    def test_tc2_011_workspace_build(self):
        self.assertEqual(build_run(self.tmp), 0)

        for package in ("core", "world", "app"):
            self.assertTrue((self.tmp / package / "target" / "ir" / "main.json").is_file())

    def test_tc2_012_package_build(self):
        self.assertEqual(build_run(self.tmp, package="world"), 0)

        self.assertTrue((self.tmp / "world" / "target" / "ir" / "main.json").is_file())
        self.assertFalse((self.tmp / "app" / "target" / "ir" / "main.json").exists())

    def test_tc2_013_workspace_check(self):
        self.assertEqual(check_run(self.tmp), 0)

    def test_tc2_014_workspace_test(self):
        self.assertEqual(suite_run(self.tmp), 0)

    def test_tc2_015_workspace_run(self):
        build_run(self.tmp)

        self.assertEqual(run_run(self.tmp), 0)

    def test_tc2_016_default_package_resolution(self):
        workspace = PackageGraphService().discover(self.tmp)

        self.assertEqual(workspace.default_package.name, "app")

    def test_tc2_017_incremental_build(self):
        build_run(self.tmp)
        cache_before = (self.tmp / "app" / "target" / ".reason_build_cache").read_text()
        (self.tmp / "world" / "src" / "main.rsn").write_text(MAIN.format(name="world").replace("goal", "goal2"), encoding="utf-8")
        build_run(self.tmp)
        cache_after = (self.tmp / "app" / "target" / ".reason_build_cache").read_text()

        self.assertNotEqual(cache_before, cache_after)

    def test_tc2_018_platform_diagnostic_integration(self):
        diagnostic = diagnostic_from_workspace_error(UnknownPackageError("ghost"))

        self.assertEqual(diagnostic.to_dict()["schema"], PLATFORM_DIAGNOSTIC_SCHEMA)
        self.assertEqual(diagnostic.code, "UnknownPackage")

    def test_tc2_019_lsp_package_graph_integration(self):
        server = ReasonScriptLanguageServer()
        server.scan_workspace(self.tmp)

        self.assertIsNotNone(server.package_graph)
        self.assertEqual(server.package_graph.build_order, ("core", "world", "app"))

    def test_tc2_020_ide_workspace_integration(self):
        ide = ReasonScriptIde(self.tmp / "app" / "src")

        self.assertEqual(ide.workspace.root, self.tmp.resolve())
        self.assertEqual(ide.build().status.value, "success")


def _workspace(root: Path) -> None:
    (root / "reason.workspace.toml").write_text(
        """\
[workspace]
members = ["core", "world", "app"]
default_package = "app"
""",
        encoding="utf-8",
    )
    _package(root / "core", "core")
    _package(root / "world", "world", deps='core = { path = "../core" }\n')
    _package(root / "app", "app", deps='world = { path = "../world" }\n')


def _package(root: Path, name: str, deps: str = "") -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "target" / "ast").mkdir(parents=True, exist_ok=True)
    (root / "target" / "ir").mkdir(parents=True, exist_ok=True)
    (root / "target" / "metadata").mkdir(parents=True, exist_ok=True)
    (root / "target" / "runtime").mkdir(parents=True, exist_ok=True)
    _write_manifest(root, name, deps)
    (root / "src" / "main.rsn").write_text(MAIN.format(name=name), encoding="utf-8")
    (root / "tests" / "sample_test.rsn").write_text(TEST.format(name=name), encoding="utf-8")


def _write_manifest(root: Path, name: str, deps: str = "") -> None:
    dependencies = f"\n[dependencies]\n{deps}" if deps else ""
    (root / "reason.toml").write_text(
        f"""\
[package]
name = "{name}"
version = "0.1.0"

[compiler]
language_core = "0.7"
platform = "0.2"

[runtime]
backend = "RuntimeReal"
{dependencies}""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
