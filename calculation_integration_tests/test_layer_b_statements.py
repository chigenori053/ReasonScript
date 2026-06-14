import unittest

from frontend.language_surface import (
    AssignmentStatementNode,
    ExpressionStatementNode,
    IfStatementNode,
    LetStatementNode,
    MatchStatementNode,
    ResultStatementNode,
    parse,
)


class LayerBStatementIntegrationTests(unittest.TestCase):
    def test_b_001_through_b_005_allowed_statements(self):
        calculation = parse(
            """
            module calculation_body {
                attribute state
                calculation Risk {
                    let score = 1
                    score = score + 1
                    if score > 80 {
                        score = 80
                    }
                    match state {
                        High => normalize(score)
                        _ => normalize(state)
                    }
                    result = score
                }
            }
            """
        ).modules[0].body[-1]
        self.assertEqual(
            tuple(type(statement) for statement in calculation.body),
            (
                LetStatementNode,
                AssignmentStatementNode,
                IfStatementNode,
                MatchStatementNode,
                ResultStatementNode,
            ),
        )
        self.assertIsInstance(
            calculation.body[3].arms[0].body[0], ExpressionStatementNode
        )

    def test_control_flow_may_terminate_each_path_with_result(self):
        calculation = parse(
            """
            module branching {
                attribute risk
                calculation Select {
                    match risk {
                        High => result = 10
                        Low => result = 1
                    }
                }
            }
            """
        ).modules[0].body[-1]
        self.assertIsInstance(calculation.body[-1], MatchStatementNode)


if __name__ == "__main__":
    unittest.main()
