import dataclasses
import unittest

from frontend.language_surface import (
    ActionNode,
    AttributeNode,
    CalculationNode,
    ConceptNode,
    ConstraintNode,
    EventNode,
    GoalNode,
    ImportNode,
    LetNode,
    MatchArmNode,
    MatchNode,
    ModuleNode,
    ObjectNode,
    ProgramNode,
    RelationNode,
    RelationType,
    ResultStatementNode,
    TransitionNode,
    Visibility,
    parse_expression,
    parse_pattern,
    validate,
)


class LayerANodeGenerationTests(unittest.TestCase):
    def test_a_001_through_a_008_all_primary_nodes_are_immutable(self):
        nodes = (
            ImportNode(("finance", "loan")),
            ConceptNode("Person"),
            ObjectNode("User"),
            EventNode("Login"),
            ActionNode("Approve"),
            AttributeNode("Age"),
            AttributeNode("state"),
            GoalNode("LoanApproval"),
            ConstraintNode("Adult"),
            RelationNode("User", RelationType.IS_A, "Person"),
            TransitionNode("ApproveFlow", "Draft", "Approved"),
            CalculationNode(
                "RiskScore",
                None,
                (
                    LetNode("income", parse_expression("100")),
                    MatchNode(
                        parse_expression("state"),
                        (
                            MatchArmNode(
                                parse_pattern("_"),
                                (LetNode("x", parse_expression("0")),),
                            ),
                        ),
                    ),
                    ResultStatementNode(parse_expression("income * 2")),
                ),
            ),
        )
        program = ProgramNode(
            (
                ModuleNode(
                    "finance",
                    Visibility.PUBLIC,
                    nodes,
                ),
            )
        )
        validate(program)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            program.modules = ()

    def test_source_order_is_preserved(self):
        body = (
            LetNode("a", parse_expression("1")),
            LetNode("b", parse_expression("2")),
            LetNode("c", parse_expression("3")),
            ResultStatementNode(parse_expression("c")),
        )
        calculation = CalculationNode("Ordered", None, body)
        self.assertEqual(
            [node.identifier for node in calculation.body[:-1]], ["a", "b", "c"]
        )


if __name__ == "__main__":
    unittest.main()
