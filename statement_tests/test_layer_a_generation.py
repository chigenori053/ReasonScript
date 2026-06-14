import unittest

from frontend.language_surface import (
    AssignmentStatementNode,
    ExpressionStatementNode,
    GoalStatementNode,
    IfStatementNode,
    LetStatementNode,
    MatchStatementNode,
    ReachStatementNode,
    RequireStatementNode,
    ResultStatementNode,
    parse,
)


SOURCE = """
module workflow {
    constraint Adult
    goal Approved
    transition Approve {
        Draft -> ApprovedState
        require Adult
        goal Approved
        reach Approved
        notify(user)
        if valid {
            publish(order)
        }
        match state {
            Draft => publish(order)
        }
    }
    calculation Risk {
        let score = 100
        score = score + 1
        notify(score)
        if score > 80 {
            score = score + 1
        }
        match score {
            101 => notify(score)
        }
        result = score
    }
}
"""


class LayerAStatementGenerationTests(unittest.TestCase):
    def test_a_001_through_a_009_statement_nodes(self):
        module = parse(SOURCE).modules[0]
        transition = module.body[2]
        calculation = module.body[3]
        expected_transition = (
            RequireStatementNode,
            GoalStatementNode,
            ReachStatementNode,
            ExpressionStatementNode,
            IfStatementNode,
            MatchStatementNode,
        )
        self.assertEqual(
            tuple(type(statement) for statement in transition.body),
            expected_transition,
        )
        expected_calculation = (
            LetStatementNode,
            AssignmentStatementNode,
            ExpressionStatementNode,
            IfStatementNode,
            MatchStatementNode,
            ResultStatementNode,
        )
        self.assertEqual(
            tuple(type(statement) for statement in calculation.body),
            expected_calculation,
        )


if __name__ == "__main__":
    unittest.main()
