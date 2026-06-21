"""VSCode Extension Phase 1 Conformance Tests - VSX1-001 through VSX1-020."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from frontend.lsp import ReasonScriptLanguageServer
from toolchain.build_cmd import run as build_run
from toolchain.check_cmd import run as check_run
from toolchain.run_cmd import run as run_run
from toolchain.runner_cmd import run as suite_run
from toolchain.workspace import PackageGraphService


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "vscode-extension"


MAIN = """\
package {name}
module main {{
    fn run(goal) {{
        return goal
    }}
}}
"""


class VSCodeExtensionPhase1Tests(unittest.TestCase):
    def setUp(self):
        self.package = json.loads((EXT / "package.json").read_text(encoding="utf-8"))
        self.extension_source = (EXT / "src" / "extension.ts").read_text(encoding="utf-8")

    def test_vsx1_001_extension_activation(self):
        self.assertIn("onLanguage:reasonscript", self.package["activationEvents"])
        self.assertIn("workspaceContains:reason.toml", self.package["activationEvents"])
        self.assertIn("workspaceContains:reason.workspace.toml", self.package["activationEvents"])

    def test_vsx1_002_workspace_detection(self):
        source = (EXT / "src" / "workspace" / "workspace.ts").read_text(encoding="utf-8")

        self.assertIn("reason.workspace.toml", source)
        self.assertIn("reason.toml", source)

    def test_vsx1_003_language_registration(self):
        language = self.package["contributes"]["languages"][0]

        self.assertEqual(language["id"], "reasonscript")
        self.assertEqual(language["extensions"], [".rsn"])

    def test_vsx1_004_lsp_startup(self):
        source = (EXT / "src" / "lsp" / "client.ts").read_text(encoding="utf-8")

        self.assertIn("frontend.lsp", source)
        self.assertIn("TransportKind.stdio", source)

    def test_vsx1_005_diagnostics(self):
        server = ReasonScriptLanguageServer()
        state = server.open_document("file:///bad.rsn", "@@invalid@@")

        self.assertTrue(state.diagnostics)

    def test_vsx1_006_hover(self):
        server = ReasonScriptLanguageServer()
        uri = "file:///main.rsn"
        server.open_document(uri, MAIN.format(name="app"))

        self.assertIsNotNone(server.hover(uri, 1, 8))

    def test_vsx1_007_completion(self):
        server = ReasonScriptLanguageServer()
        completions = server.completion("file:///main.rsn", 0, 0)

        self.assertIn("runtime.plan", [item.label for item in completions])
        self.assertIn("Agent", [item.label for item in completions])

    def test_vsx1_008_definition(self):
        server = ReasonScriptLanguageServer()
        uri = "file:///main.rsn"
        server.open_document(uri, MAIN.format(name="app"))

        self.assertIsNotNone(server.definition(uri, 1, 8))

    def test_vsx1_009_references(self):
        server = ReasonScriptLanguageServer()
        uri = "file:///main.rsn"
        server.open_document(uri, MAIN.format(name="app"))

        self.assertTrue(server.references(uri, 1, 8))

    def test_vsx1_010_workspace_symbols(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _package(root, "app")
            symbols = ReasonScriptLanguageServer().scan_workspace(root)

        self.assertIn("main", [symbol.name for symbol in symbols])

    def test_vsx1_011_build_command(self):
        self.assertIn("reasonscript.build", [item["command"] for item in self.package["contributes"]["commands"]])
        self.assertIn("reasonExecutable()", (EXT / "src" / "commands" / "toolchain.ts").read_text(encoding="utf-8"))

    def test_vsx1_012_run_command(self):
        self.assertIn("reasonscript.run", [item["command"] for item in self.package["contributes"]["commands"]])

    def test_vsx1_013_test_command(self):
        self.assertIn("reasonscript.test", [item["command"] for item in self.package["contributes"]["commands"]])

    def test_vsx1_014_check_command(self):
        self.assertIn("reasonscript.check", [item["command"] for item in self.package["contributes"]["commands"]])

    def test_vsx1_015_output_channels(self):
        source = (EXT / "src" / "commands" / "toolchain.ts").read_text(encoding="utf-8")

        self.assertIn("ReasonScript Build", source)
        self.assertIn("ReasonScript Run", source)
        self.assertIn("ReasonScript Test", source)
        self.assertIn("ReasonScript Check", source)

    def test_vsx1_016_status_bar(self):
        source = self.extension_source + (EXT / "src" / "commands" / "toolchain.ts").read_text(encoding="utf-8")

        self.assertIn("ReasonScript Ready", source)
        self.assertIn("Build Success", source)
        self.assertIn("Build Failed", source)
        self.assertIn("Tests Passed", source)
        self.assertIn("Tests Failed", source)

    def test_vsx1_017_package_graph_awareness(self):
        source = (EXT / "src" / "workspace" / "packageGraph.ts").read_text(encoding="utf-8")

        self.assertIn("PackageGraph", source)
        self.assertIn("load_package_graph", source)

    def test_vsx1_018_workspace_project_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _package(root, "app")
            self.assertEqual(check_run(root), 0)
            self.assertEqual(build_run(root), 0)
            self.assertEqual(run_run(root), 0)

    def test_vsx1_019_multi_package_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _workspace(root)
            graph = PackageGraphService().discover(root).graph
            self.assertEqual(graph.build_order, ("core", "app"))
            self.assertEqual(build_run(root, package="app"), 0)

    def test_vsx1_020_end_to_end_vscode_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _package(root, "app", include_test=True)
            server = ReasonScriptLanguageServer()
            symbols = server.scan_workspace(root)
            self.assertTrue(symbols)
            self.assertEqual(check_run(root), 0)
            self.assertEqual(build_run(root), 0)
            self.assertEqual(suite_run(root), 0)
            self.assertEqual(run_run(root), 0)

    def test_vsxp_001_compile_script_present(self):
        self.assertEqual(self.package["scripts"]["compile"], "tsc -p ./")

    def test_vsxp_002_package_argument_support(self):
        toolchain_source = (EXT / "src" / "commands" / "toolchain.ts").read_text(encoding="utf-8")

        self.assertIn("const args: string[] = [command];", toolchain_source)
        self.assertIn('args.push("--package", packageName);', toolchain_source)

    def test_vsxp_003_workspace_command_support(self):
        tasks_source = (EXT / "src" / "commands" / "tasks.ts").read_text(encoding="utf-8")

        self.assertIn("const args: string[] = [definition.command];", tasks_source)
        self.assertIn('args.push("--package", definition.package);', tasks_source)

    def test_vsxp_004_package_script_present(self):
        self.assertEqual(self.package["scripts"]["package"], "vsce package")


def _package(root: Path, name: str, include_test: bool = False) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "target" / "ast").mkdir(parents=True, exist_ok=True)
    (root / "target" / "ir").mkdir(parents=True, exist_ok=True)
    (root / "target" / "metadata").mkdir(parents=True, exist_ok=True)
    (root / "target" / "runtime").mkdir(parents=True, exist_ok=True)
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
""",
        encoding="utf-8",
    )
    (root / "src" / "main.rsn").write_text(MAIN.format(name=name), encoding="utf-8")
    if include_test:
        (root / "tests" / "sample_test.rsn").write_text(MAIN.format(name=name), encoding="utf-8")


def _workspace(root: Path) -> None:
    (root / "reason.workspace.toml").write_text(
        """\
[workspace]
members = ["core", "app"]
default_package = "app"
""",
        encoding="utf-8",
    )
    _package(root / "core", "core")
    _package(root / "app", "app")
    with (root / "app" / "reason.toml").open("a", encoding="utf-8") as handle:
        handle.write('\n[dependencies]\ncore = { path = "../core" }\n')


if __name__ == "__main__":
    unittest.main()
