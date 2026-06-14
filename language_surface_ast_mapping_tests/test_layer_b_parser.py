import unittest

from frontend.language_surface import (
    CalculationNode,
    IfNode,
    MatchNode,
    RelationNode,
    TransitionNode,
    parse,
    tokenize,
)


SOURCE = """
pub module finance {
    import common.money as money
    concept Person
    object User
    event Login
    action Approve
    attribute Age
    attribute band
    attribute state
    goal LoanApproval
    goal value
    constraint Adult
    User IsA Person

    transition ApproveFlow {
        Draft -> Approved
        requires Adult
        goal LoanApproval
    }

    calculation RiskScore goal:value {
        let income = 100
        let factor = 2
        if income > 80 {
            band = 3
        }
        elif income > 50 {
            band = 2
        }
        else {
            band = 1
        }
        match band {
            3 => approve()
            _ => reject()
        }
        result = income * factor
    }
}

module audit {
    event Recorded
    goal AuditComplete
}
"""


class LayerBParserMappingTests(unittest.TestCase):
    def test_source_passes_through_positioned_lexer(self):
        tokens = tokenize("pub module finance {\n}")
        self.assertEqual(tokens[0].value, "pub")
        self.assertEqual(tokens[0].line, 1)
        self.assertEqual(tokens[3].value, "{")
        self.assertEqual(tokens[-1].token_type.value, "EOF")

    def test_b_001_and_b_002_single_and_multiple_modules(self):
        program = parse(SOURCE)
        self.assertEqual([module.name for module in program.modules], ["finance", "audit"])
        self.assertEqual(program.modules[0].visibility.value, "Public")
        self.assertEqual(program.modules[1].visibility.value, "Private")

    def test_b_003_through_b_007_nested_constructs_map_once(self):
        module = parse(SOURCE).modules[0]
        self.assertEqual(sum(isinstance(node, RelationNode) for node in module.body), 1)
        self.assertEqual(sum(isinstance(node, TransitionNode) for node in module.body), 1)
        calculations = [node for node in module.body if isinstance(node, CalculationNode)]
        self.assertEqual(len(calculations), 1)
        calculation = calculations[0]
        self.assertEqual(sum(isinstance(node, IfNode) for node in calculation.body), 1)
        self.assertEqual(sum(isinstance(node, MatchNode) for node in calculation.body), 1)
        conditional = next(node for node in calculation.body if isinstance(node, IfNode))
        self.assertEqual(len(conditional.elif_branches), 1)
        self.assertIsNotNone(conditional.else_branch)

    def test_repeated_parse_is_structurally_equal(self):
        self.assertEqual(parse(SOURCE), parse(SOURCE))


if __name__ == "__main__":
    unittest.main()
