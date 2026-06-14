import json
import unittest

from conformance.framework import ROOT, validate_reason_ir
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    IdentifierNode,
    QualifiedIdentifierNode,
    SurfaceSyntaxError,
    compile_program,
    execution_plan_for,
    expression_from_json,
    parse,
    parse_expression,
    project_program,
    to_json_value,
)


PUBLIC_FINANCE = """
pub module finance {
    goal LoanApproval
    pub calculation RiskScore {
        result = 1
    }
}
"""


class LayerANamespaceTests(unittest.TestCase):
    def test_a_001_and_a_002_module_namespace_and_symbol_registration(self):
        program = parse(PUBLIC_FINANCE)
        semantic = project_program(program)[0]
        metadata = {item.key: item.value for item in semantic.metadata}
        self.assertEqual(metadata["namespace"], "finance")

    def test_a_003_qualified_name_node_and_round_trip(self):
        expression = parse_expression("finance::RiskScore")
        node = expression.expression
        self.assertIsInstance(node, QualifiedIdentifierNode)
        self.assertEqual(node.path, ("finance",))
        value = to_json_value(expression)
        self.assertEqual(expression_from_json(json.loads(json.dumps(value))), expression)


class LayerBImportTests(unittest.TestCase):
    def test_b_001_import_exists_and_metadata_is_serialized(self):
        program = parse(
            PUBLIC_FINANCE
            + """
            module app {
                import finance
                calculation Use {
                    result = RiskScore
                }
            }
            """
        )
        imported = program.modules[1].body[0]
        self.assertEqual(imported.resolution.namespace, "finance")
        self.assertIn("RiskScore", imported.resolution.exposed_names)

    def test_b_002_alias_import_resolves_to_canonical_name(self):
        program = parse(
            PUBLIC_FINANCE
            + """
            module app {
                import finance as loan
                calculation Use {
                    result = loan::RiskScore
                }
            }
            """
        )
        expression = program.modules[1].body[1].body[0].expression.expression
        self.assertEqual(expression.resolved_name, "finance::RiskScore")

    def test_b_003_private_symbol_is_not_importable(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "NS-050"):
            parse(
                """
                pub module finance {
                    calculation InternalRisk {
                        result = 1
                    }
                }
                module app {
                    import finance.InternalRisk
                    calculation Use {
                        result = InternalRisk
                    }
                }
                """
            )


class LayerCResolutionTests(unittest.TestCase):
    def test_c_001_local_scope_precedes_module_and_import(self):
        program = parse(
            PUBLIC_FINANCE
            + """
            module app {
                import finance
                calculation Use {
                    let RiskScore = 2
                    result = RiskScore
                }
            }
            """
        )
        result = program.modules[1].body[1].body[-1].expression.expression
        self.assertIsInstance(result, IdentifierNode)

    def test_c_002_and_c_003_module_then_import_scope(self):
        parse(
            PUBLIC_FINANCE
            + """
            module app {
                import finance
                goal LocalGoal
                calculation Use {
                    let local = LocalGoal
                    result = RiskScore
                }
            }
            """
        )

    def test_c_004_qualified_name(self):
        program = parse(
            PUBLIC_FINANCE
            + """
            module app {
                calculation Use {
                    result = finance::RiskScore
                }
            }
            """
        )
        node = program.modules[1].body[0].body[0].expression.expression
        self.assertEqual(node.resolved_name, "finance::RiskScore")


class LayerDConflictTests(unittest.TestCase):
    def assert_namespace_error(self, source: str, code: str):
        with self.assertRaisesRegex(SurfaceSyntaxError, code):
            parse(source)

    def test_d_001_duplicate_symbol(self):
        self.assert_namespace_error(
            """
            module invalid {
                goal Same
                calculation Same {
                    result = 1
                }
            }
            """,
            "NS-001",
        )

    def test_d_002_alias_conflict(self):
        self.assert_namespace_error(
            PUBLIC_FINANCE
            + """
            module app {
                goal loan
                import finance as loan
            }
            """,
            "NS-021",
        )

    def test_d_003_ambiguous_symbol(self):
        self.assert_namespace_error(
            """
            pub module finance {
                pub calculation RiskScore {
                    result = 1
                }
            }
            pub module risk {
                pub calculation RiskScore {
                    result = 2
                }
            }
            module app {
                import finance
                import risk
            }
            """,
            "NS-040",
        )

    def test_missing_import_and_qualified_target(self):
        self.assert_namespace_error(
            "module app {\nimport Missing\n}",
            "NS-020",
        )
        self.assert_namespace_error(
            PUBLIC_FINANCE
            + """
            module app {
                import finance.Missing
            }
            """,
            "NS-020",
        )
        self.assert_namespace_error(
            PUBLIC_FINANCE
            + """
            module app {
                calculation Use {
                    result = finance::Missing
                }
            }
            """,
            "NS-030",
        )


class LayerECompilerCompatibilityTests(unittest.TestCase):
    def test_e_001_through_e_004_serialization_projection_ir_and_plan(self):
        program = parse(
            PUBLIC_FINANCE
            + """
            module app {
                import finance as loan
                calculation Use {
                    result = loan::RiskScore
                }
            }
            """
        )
        value = to_json_value(program)
        SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
            value, "language_surface_ast.schema.json"
        )
        semantic = project_program(program)[1]
        result_transition = semantic.declarations[-1]
        expression = result_transition.effect["expression"]["expression"]
        self.assertEqual(expression["resolved_name"], "finance::RiskScore")
        reason_ir = compile_program(program)[1]
        validate_reason_ir(reason_ir)
        plan = execution_plan_for(reason_ir)
        SchemaValidator(ROOT / "schemas").validate_file(
            plan, "execution_plan.schema.json"
        )


if __name__ == "__main__":
    unittest.main()
