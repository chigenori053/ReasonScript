"""VSCode Extension Phase 1.3 Conformance Tests - VSXP13-001 through VSXP13-012."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "vscode-extension"


class VSCodeExtensionPhase13Tests(unittest.TestCase):
    def setUp(self):
        self.package = json.loads((EXT / "package.json").read_text(encoding="utf-8"))
        self.extension_source = (EXT / "src" / "extension.ts").read_text(encoding="utf-8")
        self.toolchain_source = (EXT / "src" / "commands" / "toolchain.ts").read_text(encoding="utf-8")
        self.commands = [item["command"] for item in self.package["contributes"]["commands"]]

    # -------------------------------------------------------------------------
    # VSXP13-001  Module Load Success
    # -------------------------------------------------------------------------
    def test_vsxp13_001_module_load_success(self):
        """toolchain.ts logs module load."""
        self.assertIn("[ReasonScript] toolchain module loaded", self.toolchain_source)

    # -------------------------------------------------------------------------
    # VSXP13-002  OutputChannel Lazy Initialization
    # -------------------------------------------------------------------------
    def test_vsxp13_002_outputchannel_lazy_initialization(self):
        """toolchain.ts uses lazy initialization for outputChannels."""
        self.assertIn("function getOutputChannels()", self.toolchain_source)
        self.assertIn("let _outputChannels", self.toolchain_source)
        self.assertNotIn("export const outputChannels: Record<ToolchainCommand, vscode.OutputChannel> = {", self.toolchain_source)

    # -------------------------------------------------------------------------
    # VSXP13-003  Activation Start Logging
    # -------------------------------------------------------------------------
    def test_vsxp13_003_activation_start_logging(self):
        """extension.ts logs activation start."""
        self.assertIn("[ReasonScript] activate start", self.extension_source)

    # -------------------------------------------------------------------------
    # VSXP13-004  Command Registration Logging
    # -------------------------------------------------------------------------
    def test_vsxp13_004_command_registration_logging(self):
        """extension.ts logs command registration."""
        self.assertIn("[ReasonScript] commands registered", self.extension_source)

    # -------------------------------------------------------------------------
    # VSXP13-005  Activation Complete Logging
    # -------------------------------------------------------------------------
    def test_vsxp13_005_activation_complete_logging(self):
        """extension.ts logs activation complete."""
        self.assertIn("[ReasonScript] activate complete", self.extension_source)

    # -------------------------------------------------------------------------
    # VSXP13-006  Extension Host Visibility
    # -------------------------------------------------------------------------
    def test_vsxp13_006_extension_host_visibility(self):
        """extension.ts uses console.log for visibility in Extension Host."""
        self.assertIn('console.log("[ReasonScript] activate start");', self.extension_source)

    # -------------------------------------------------------------------------
    # VSXP13-007  Build Command Registration
    # -------------------------------------------------------------------------
    def test_vsxp13_007_build_command_registration(self):
        self.assertIn("reasonscript.build", self.commands)

    # -------------------------------------------------------------------------
    # VSXP13-008  Run Command Registration
    # -------------------------------------------------------------------------
    def test_vsxp13_008_run_command_registration(self):
        self.assertIn("reasonscript.run", self.commands)

    # -------------------------------------------------------------------------
    # VSXP13-009  Test Command Registration
    # -------------------------------------------------------------------------
    def test_vsxp13_009_test_command_registration(self):
        self.assertIn("reasonscript.test", self.commands)

    # -------------------------------------------------------------------------
    # VSXP13-010  Check Command Registration
    # -------------------------------------------------------------------------
    def test_vsxp13_010_check_command_registration(self):
        self.assertIn("reasonscript.check", self.commands)

    # -------------------------------------------------------------------------
    # VSXP13-011  LSP Failure Isolation Regression
    # -------------------------------------------------------------------------
    def test_vsxp13_011_lsp_failure_isolation_regression(self):
        """Ensure Phase 1.2 LSP failure isolation is intact."""
        register_pos = self.extension_source.index("registerToolchainCommands")
        try_pos = self.extension_source.index("try {")
        self.assertLess(register_pos, try_pos)
        self.assertIn("} catch (err) {", self.extension_source)

    # -------------------------------------------------------------------------
    # VSXP13-012  End-to-End Activation
    # -------------------------------------------------------------------------
    def test_vsxp13_012_end_to_end_activation(self):
        """Lifecycle logs must be in the correct order."""
        start_pos = self.extension_source.index("[ReasonScript] activate start")
        reg_pos = self.extension_source.index("[ReasonScript] commands registered")
        lsp_pos = self.extension_source.index("[ReasonScript] lsp startup")
        complete_pos = self.extension_source.index("[ReasonScript] activate complete")
        
        self.assertLess(start_pos, reg_pos)
        self.assertLess(reg_pos, lsp_pos)
        self.assertLess(lsp_pos, complete_pos)


if __name__ == "__main__":
    unittest.main()
