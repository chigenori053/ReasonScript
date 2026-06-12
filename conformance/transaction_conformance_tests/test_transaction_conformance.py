import subprocess
import unittest

from conformance.framework import ROOT, execute_transaction_fixture, load_json


class TransactionConformanceTests(unittest.TestCase):
    def test_transaction_fixtures_match_expected_history(self):
        directory = ROOT / "conformance" / "fixtures" / "transactions"
        for path in sorted(directory.glob("*.json")):
            fixture = load_json(path)
            self.assertEqual(execute_transaction_fixture(fixture), fixture["expected"], path.name)

    def test_reference_runtime_transaction_suite(self):
        completed = subprocess.run(
            [
                "cargo",
                "test",
                "--quiet",
                "--manifest-path",
                "HybridRuntime/Cargo.toml",
                "--test",
                "runtime_api_phase_3_transaction_validation",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
