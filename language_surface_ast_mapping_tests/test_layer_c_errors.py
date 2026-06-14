import unittest

from frontend.language_surface import (
    CalculationNode,
    MatchNode,
    ModuleNode,
    ProgramNode,
    RelationNode,
    RelationType,
    SurfaceSyntaxError,
    SurfaceValidationError,
    ResultStatementNode,
    TransitionNode,
    Visibility,
    parse,
    parse_expression,
    validate,
)


class LayerCInvalidMappingTests(unittest.TestCase):
    def test_c_001_missing_identifier(self):
        with self.assertRaises(SurfaceSyntaxError):
            parse("module finance {\nconcept\n}")

    def test_c_002_missing_relation_target(self):
        with self.assertRaises(SurfaceSyntaxError):
            parse("module finance {\nconcept User\nUser IsA\n}")

    def test_c_003_missing_transition_state(self):
        invalid = ProgramNode(
            (
                ModuleNode(
                    "finance",
                    Visibility.PRIVATE,
                    (TransitionNode("Approve", "", "Approved"),),
                ),
            )
        )
        with self.assertRaisesRegex(SurfaceValidationError, "T-002"):
            validate(invalid)

    def test_c_004_missing_calculation_result(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CAL-010"):
            parse("module finance {\ncalculation Risk {\nlet x = 1\n}\n}")

    def test_c_005_empty_match(self):
        invalid = ProgramNode(
            (
                ModuleNode(
                    "finance",
                    Visibility.PRIVATE,
                    (
                        CalculationNode(
                            "Risk",
                            None,
                            (
                                MatchNode(parse_expression("state"), ()),
                                ResultStatementNode(parse_expression("1")),
                            ),
                        ),
                    ),
                ),
            )
        )
        with self.assertRaisesRegex(SurfaceValidationError, "MT-002"):
            validate(invalid)

    def test_ast_v004_reference_resolution(self):
        invalid = ProgramNode(
            (
                ModuleNode(
                    "finance",
                    Visibility.PRIVATE,
                    (RelationNode("Missing", RelationType.IS_A, "AlsoMissing"),),
                ),
            )
        )
        with self.assertRaisesRegex(SurfaceValidationError, "AST-V004"):
            validate(invalid)


if __name__ == "__main__":
    unittest.main()
