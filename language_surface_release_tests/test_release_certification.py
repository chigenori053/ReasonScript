import json
import unittest

from conformance.framework import ROOT, validate_reason_ir
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    compile_program,
    execution_plan_for,
    from_json_value,
    parse,
    project_program,
    to_json_value,
)


SOURCE = """
pub module finance {
    goal LoanApproval
    constraint Adult
    pub calculation RiskScore -> Float {
        let score: Float = 0.8
        result = score
    }
}

module app {
    import finance as loan
    calculation Evaluate -> Float {
        let target: Goal = finance::LoanApproval
        result = loan::RiskScore
    }
}
"""


class LanguageSurfaceReleaseCertificationTests(unittest.TestCase):
    def test_release_manifest_is_fixed(self):
        manifest = json.loads(
            (ROOT / "release/language-surface-v0.1/manifest.json").read_text()
        )
        release = manifest["release"]
        self.assertEqual(
            release["version"], "reasonscript-language-surface/0.1"
        )
        self.assertEqual(release["status"], "released")
        self.assertEqual(release["date"], "2026-06-14")
        for key in (
            "normative_specification",
            "validation_report",
            "validation_results",
            "release_gate",
        ):
            self.assertTrue((ROOT / manifest[key]).is_file(), key)

        results = json.loads((ROOT / manifest["validation_results"]).read_text())
        self.assertEqual(results["release"], release["version"])
        self.assertEqual(results["result"], "pass")

    def test_normative_release_pipeline_is_deterministic(self):
        first = parse(SOURCE)
        second = parse(SOURCE)
        self.assertEqual(first, second)
        self.assertEqual(project_program(first), project_program(second))
        self.assertEqual(compile_program(first), compile_program(second))

    def test_release_serialization_and_interfaces(self):
        program = parse(SOURCE)
        value = to_json_value(program)
        SchemaValidator(ROOT / "frontend/schemas").validate_file(
            value, "language_surface_ast.schema.json"
        )
        self.assertEqual(from_json_value(json.loads(json.dumps(value))), program)

        for reason_ir in compile_program(program):
            validate_reason_ir(reason_ir)
            SchemaValidator(ROOT / "schemas").validate_file(
                reason_ir, "reason_ir.schema.json"
            )
            plan = execution_plan_for(reason_ir)
            SchemaValidator(ROOT / "schemas").validate_file(
                plan, "execution_plan.schema.json"
            )


if __name__ == "__main__":
    unittest.main()
