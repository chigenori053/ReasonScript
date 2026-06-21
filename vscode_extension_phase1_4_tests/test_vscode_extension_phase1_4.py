"""VSCode Extension Phase 1.4 Conformance Tests - VSXP14-001 through VSXP14-010.

Phase 1.4 resolves the activation failure:
    Cannot find module 'vscode-languageclient/node'

Coverage:
    VSXP14-001  Runtime Dependency Audit
    VSXP14-002  Manifest Validation
    VSXP14-003  Dependency Presence
    VSXP14-004  Activation Success (structural)
    VSXP14-005  Activation Diagnostics
    VSXP14-006  Build Command
    VSXP14-007  Run Command
    VSXP14-008  Test Command
    VSXP14-009  Check Command
    VSXP14-010  End-to-End Workflow (structural)
"""

from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "vscode-extension"
VSIX_PATH = EXT / "reasonscript-0.1.7.vsix"

# VSIX内に必須のランタイム依存関係
REQUIRED_RUNTIME_MODULES = [
    "extension/node_modules/vscode-languageclient/",
    "extension/node_modules/vscode-jsonrpc/",
    "extension/node_modules/vscode-languageserver-protocol/",
    "extension/node_modules/vscode-languageserver-types/",
]

# アクティベーションライフサイクルログ
REQUIRED_ACTIVATION_LOGS = [
    "[ReasonScript] activate start",
    "[ReasonScript] commands registered",
    "[ReasonScript] lsp startup",
    "[ReasonScript] activate complete",
]

# 登録必須コマンド
REQUIRED_COMMANDS = [
    "reasonscript.build",
    "reasonscript.run",
    "reasonscript.test",
    "reasonscript.check",
]


class VSCodeExtensionPhase14Tests(unittest.TestCase):
    """Phase 1.4 コンフォーマンステスト: VSIX パッケージング修正 & アクティベーション検証."""

    def setUp(self):
        self.package = json.loads((EXT / "package.json").read_text(encoding="utf-8"))
        self.extension_source = (EXT / "src" / "extension.ts").read_text(encoding="utf-8")
        self.toolchain_source = (EXT / "src" / "commands" / "toolchain.ts").read_text(encoding="utf-8")
        self.commands = [item["command"] for item in self.package["contributes"]["commands"]]

    # -------------------------------------------------------------------------
    # VSXP14-001  Runtime Dependency Audit
    # -------------------------------------------------------------------------
    def test_vsxp14_001_runtime_dependency_audit(self):
        """VSIX に activation-critical な依存関係が全て含まれていること."""
        self.assertTrue(VSIX_PATH.exists(), f"VSIX が存在しない: {VSIX_PATH}")

        with zipfile.ZipFile(VSIX_PATH, "r") as zf:
            names = zf.namelist()

        for module in REQUIRED_RUNTIME_MODULES:
            matched = [n for n in names if n.startswith(module)]
            self.assertGreater(
                len(matched), 0,
                f"VSIX に必須モジュールが含まれていない: {module}\n"
                f"含まれているnode_modulesエントリ: {[n for n in names if 'node_modules' in n][:10]}"
            )

    # -------------------------------------------------------------------------
    # VSXP14-002  Package Manifest Validation
    # -------------------------------------------------------------------------
    def test_vsxp14_002_manifest_validation(self):
        """package.json のバージョンが 0.1.7 であること."""
        self.assertEqual(
            self.package["version"], "0.1.7",
            f"バージョンが 0.1.7 ではない: {self.package['version']}"
        )

    def test_vsxp14_002b_runtime_dependency_declared(self):
        """package.json の dependencies に vscode-languageclient が宣言されていること."""
        deps = self.package.get("dependencies", {})
        self.assertIn(
            "vscode-languageclient", deps,
            "vscode-languageclient が dependencies に宣言されていない"
        )

    def test_vsxp14_002c_vscodeignore_does_not_exclude_runtime_deps(self):
        """.vscodeignore がランタイム依存関係を除外していないこと."""
        vscodeignore_path = EXT / ".vscodeignore"
        if not vscodeignore_path.exists():
            return  # .vscodeignore が無い場合はデフォルト動作に任せる

        content = vscodeignore_path.read_text(encoding="utf-8")
        # ランタイム依存関係を除外するパターンが含まれていないことを確認
        forbidden_patterns = [
            "node_modules/vscode-languageclient",
            "node_modules/vscode-jsonrpc",
            "node_modules/vscode-languageserver-protocol",
            "node_modules/vscode-languageserver-types",
        ]
        for pattern in forbidden_patterns:
            # コメント行は除外して検査
            non_comment_lines = [
                line for line in content.splitlines()
                if not line.strip().startswith("#")
            ]
            for line in non_comment_lines:
                self.assertNotIn(
                    pattern, line,
                    f".vscodeignore がランタイム依存関係を除外している: {line!r}"
                )

    # -------------------------------------------------------------------------
    # VSXP14-003  Dependency Presence Validation
    # -------------------------------------------------------------------------
    def test_vsxp14_003_dependency_presence(self):
        """node_modules に activation-critical な依存関係が存在すること."""
        critical_modules = [
            "vscode-languageclient",
            "vscode-jsonrpc",
            "vscode-languageserver-protocol",
            "vscode-languageserver-types",
        ]
        node_modules = EXT / "node_modules"
        self.assertTrue(node_modules.exists(), "node_modules ディレクトリが存在しない")

        for module in critical_modules:
            module_path = node_modules / module
            self.assertTrue(
                module_path.exists(),
                f"必須モジュールが node_modules に存在しない: {module}"
            )

    # -------------------------------------------------------------------------
    # VSXP14-004  Extension Activation (structural)
    # -------------------------------------------------------------------------
    def test_vsxp14_004_activation_function_exists(self):
        """extension.ts に activate 関数が定義されていること."""
        self.assertIn(
            "export async function activate(",
            self.extension_source,
            "activate 関数が extension.ts に存在しない"
        )

    def test_vsxp14_004b_deactivate_function_exists(self):
        """extension.ts に deactivate 関数が定義されていること."""
        self.assertIn(
            "export async function deactivate(",
            self.extension_source,
            "deactivate 関数が extension.ts に存在しない"
        )

    def test_vsxp14_004c_main_entry_points_to_out(self):
        """package.json の main が ./out/extension.js を指していること."""
        self.assertEqual(
            self.package.get("main"), "./out/extension.js",
            "main エントリポイントが ./out/extension.js でない"
        )

    # -------------------------------------------------------------------------
    # VSXP14-005  Activation Diagnostics
    # -------------------------------------------------------------------------
    def test_vsxp14_005_activation_diagnostics_all_logs_present(self):
        """extension.ts に全アクティベーションライフサイクルログが存在すること."""
        for log in REQUIRED_ACTIVATION_LOGS:
            self.assertIn(
                log, self.extension_source,
                f"アクティベーションログが extension.ts に存在しない: {log!r}"
            )

    def test_vsxp14_005b_activation_log_order(self):
        """アクティベーションログが仕様通りの順序で記述されていること."""
        positions = {log: self.extension_source.index(log) for log in REQUIRED_ACTIVATION_LOGS}
        logs_sorted = sorted(REQUIRED_ACTIVATION_LOGS, key=lambda l: positions[l])
        self.assertEqual(
            logs_sorted, REQUIRED_ACTIVATION_LOGS,
            f"アクティベーションログの順序が正しくない: {logs_sorted}"
        )

    def test_vsxp14_005c_console_log_for_extension_host(self):
        """Extension Host に表示されるよう console.log を使用していること."""
        self.assertIn(
            'console.log("[ReasonScript] activate start")',
            self.extension_source,
            "console.log によるアクティベーション開始ログが存在しない"
        )

    # -------------------------------------------------------------------------
    # VSXP14-006  Build Command
    # -------------------------------------------------------------------------
    def test_vsxp14_006_build_command_registered(self):
        """reasonscript.build コマンドが登録されていること."""
        self.assertIn("reasonscript.build", self.commands)

    def test_vsxp14_006b_build_command_has_title(self):
        """reasonscript.build コマンドにタイトルが設定されていること."""
        cmd = next((c for c in self.package["contributes"]["commands"]
                    if c["command"] == "reasonscript.build"), None)
        self.assertIsNotNone(cmd, "build コマンドが見つからない")
        self.assertIn("Build", cmd.get("title", ""))

    # -------------------------------------------------------------------------
    # VSXP14-007  Run Command
    # -------------------------------------------------------------------------
    def test_vsxp14_007_run_command_registered(self):
        """reasonscript.run コマンドが登録されていること."""
        self.assertIn("reasonscript.run", self.commands)

    # -------------------------------------------------------------------------
    # VSXP14-008  Test Command
    # -------------------------------------------------------------------------
    def test_vsxp14_008_test_command_registered(self):
        """reasonscript.test コマンドが登録されていること."""
        self.assertIn("reasonscript.test", self.commands)

    # -------------------------------------------------------------------------
    # VSXP14-009  Check Command
    # -------------------------------------------------------------------------
    def test_vsxp14_009_check_command_registered(self):
        """reasonscript.check コマンドが登録されていること."""
        self.assertIn("reasonscript.check", self.commands)

    # -------------------------------------------------------------------------
    # VSXP14-010  End-to-End Workflow (structural)
    # -------------------------------------------------------------------------
    def test_vsxp14_010_lsp_failure_isolation(self):
        """LSP 起動失敗がコマンド登録を妨げないこと（try/catch による分離）."""
        # コマンド登録が LSP の try ブロックより前であることを確認
        register_pos = self.extension_source.index("registerToolchainCommands")
        try_pos = self.extension_source.index("try {")
        self.assertLess(
            register_pos, try_pos,
            "コマンド登録が LSP try ブロックより後に行われている"
        )
        self.assertIn(
            "} catch (err) {", self.extension_source,
            "LSP 失敗を捕捉する catch ブロックが存在しない"
        )

    def test_vsxp14_010b_toolchain_commands_cover_all(self):
        """toolchain.ts が全コマンド（build/run/test/check）を実装していること."""
        for cmd in ["build", "run", "test", "check"]:
            self.assertIn(
                f'"{cmd}"', self.toolchain_source,
                f"toolchain.ts に {cmd!r} コマンドの実装が見つからない"
            )

    def test_vsxp14_010c_hello_world_project_exists(self):
        """hello_world プロジェクトが存在すること（E2E検証対象）."""
        hello_world = ROOT / "hello_world"
        self.assertTrue(
            hello_world.exists(),
            "hello_world プロジェクトディレクトリが存在しない"
        )

    def test_vsxp14_010d_vsix_file_exists_and_valid(self):
        """reasonscript-0.1.7.vsix が有効な ZIP アーカイブとして存在すること."""
        self.assertTrue(VSIX_PATH.exists(), f"VSIX ファイルが存在しない: {VSIX_PATH}")
        self.assertTrue(
            zipfile.is_zipfile(VSIX_PATH),
            "VSIX ファイルが有効な ZIP アーカイブでない"
        )

    # -------------------------------------------------------------------------
    # 後方互換性: Phase 1.3 リグレッション検証
    # -------------------------------------------------------------------------
    def test_phase13_regression_module_load_log(self):
        """Phase 1.3 リグレッション: toolchain.ts のモジュールロードログが維持されていること."""
        self.assertIn("[ReasonScript] toolchain module loaded", self.toolchain_source)

    def test_phase13_regression_lazy_init(self):
        """Phase 1.3 リグレッション: OutputChannel の遅延初期化が維持されていること."""
        self.assertIn("function getOutputChannels()", self.toolchain_source)
        self.assertIn("let _outputChannels", self.toolchain_source)

    def test_phase13_regression_activation_events(self):
        """Phase 1.3 リグレッション: activationEvents が全コマンドを含んでいること."""
        events = self.package.get("activationEvents", [])
        for cmd in REQUIRED_COMMANDS:
            self.assertIn(f"onCommand:{cmd}", events)


if __name__ == "__main__":
    unittest.main(verbosity=2)
