"""VSCode Extension Phase 1.2 Conformance Tests - VSXP12-001 through VSXP12-010."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "vscode-extension"


class VSCodeExtensionPhase12Tests(unittest.TestCase):
    def setUp(self):
        self.package = json.loads((EXT / "package.json").read_text(encoding="utf-8"))
        self.extension_source = (EXT / "src" / "extension.ts").read_text(encoding="utf-8")
        self.commands = [item["command"] for item in self.package["contributes"]["commands"]]

    # -------------------------------------------------------------------------
    # VSXP12-001  Activation With LSP Success
    # -------------------------------------------------------------------------
    def test_vsxp12_001_activation_with_lsp_success(self):
        """client.start() is called and LSP Online state is declared."""
        self.assertIn("await client.start()", self.extension_source)
        self.assertIn("ReasonScript LSP Online", self.extension_source)

    # -------------------------------------------------------------------------
    # VSXP12-002  Activation With LSP Failure
    # -------------------------------------------------------------------------
    def test_vsxp12_002_activation_with_lsp_failure(self):
        """LSP startup failure path is declared (catch block and Offline state)."""
        self.assertIn("} catch (err) {", self.extension_source)
        self.assertIn("ReasonScript LSP Offline", self.extension_source)

    # -------------------------------------------------------------------------
    # VSXP12-003  Commands Survive LSP Failure
    # -------------------------------------------------------------------------
    def test_vsxp12_003_commands_survive_lsp_failure(self):
        """registerToolchainCommands() precedes the LSP try block in source order."""
        register_pos = self.extension_source.index("registerToolchainCommands")
        try_pos = self.extension_source.index("try {")
        self.assertLess(
            register_pos,
            try_pos,
            "registerToolchainCommands must appear before the LSP try block",
        )

    # -------------------------------------------------------------------------
    # VSXP12-004  Build Command Available
    # -------------------------------------------------------------------------
    def test_vsxp12_004_build_command_available(self):
        self.assertIn("reasonscript.build", self.commands)

    # -------------------------------------------------------------------------
    # VSXP12-005  Check Command Available
    # -------------------------------------------------------------------------
    def test_vsxp12_005_check_command_available(self):
        self.assertIn("reasonscript.check", self.commands)

    # -------------------------------------------------------------------------
    # VSXP12-006  Run Command Available
    # -------------------------------------------------------------------------
    def test_vsxp12_006_run_command_available(self):
        self.assertIn("reasonscript.run", self.commands)

    # -------------------------------------------------------------------------
    # VSXP12-007  Test Command Available
    # -------------------------------------------------------------------------
    def test_vsxp12_007_test_command_available(self):
        self.assertIn("reasonscript.test", self.commands)

    # -------------------------------------------------------------------------
    # VSXP12-008  Warning Notification
    # -------------------------------------------------------------------------
    def test_vsxp12_008_warning_notification(self):
        """showWarningMessage is called with the 'Language server unavailable' message."""
        self.assertIn("showWarningMessage", self.extension_source)
        self.assertIn("Language server unavailable", self.extension_source)

    # -------------------------------------------------------------------------
    # VSXP12-009  Output Logging
    # -------------------------------------------------------------------------
    def test_vsxp12_009_output_logging(self):
        """Startup, failure, and recovery messages are logged to the output channel."""
        self.assertIn("Starting language server", self.extension_source)
        self.assertIn("Language server unavailable", self.extension_source)
        self.assertIn("Toolchain commands remain available", self.extension_source)

    # -------------------------------------------------------------------------
    # VSXP12-010  End-to-End Recovery
    # -------------------------------------------------------------------------
    def test_vsxp12_010_end_to_end_recovery(self):
        """Full activation fault isolation: commands before LSP, catch block, notification."""
        # Commands registered before LSP try block
        register_pos = self.extension_source.index("registerToolchainCommands")
        try_pos = self.extension_source.index("try {")
        self.assertLess(register_pos, try_pos)

        # LSP failure is caught
        self.assertIn("} catch (err) {", self.extension_source)

        # User is notified
        self.assertIn("showWarningMessage", self.extension_source)

        # Output channel records recovery message
        self.assertIn("Toolchain commands remain available", self.extension_source)

        # All four commands remain declared in manifest
        for cmd in [
            "reasonscript.build",
            "reasonscript.run",
            "reasonscript.test",
            "reasonscript.check",
        ]:
            self.assertIn(cmd, self.commands)


if __name__ == "__main__":
    unittest.main()
