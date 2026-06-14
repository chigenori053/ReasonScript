import unittest

from frontend.language_surface import (
    IdentifierPatternNode,
    LiteralPatternNode,
    MatchNode,
    WildcardPatternNode,
    parse,
    parse_pattern,
)


class LayerCPatternTests(unittest.TestCase):
    def test_c_001_through_c_003_pattern_generation(self):
        cases = {
            "Draft": IdentifierPatternNode,
            "1": LiteralPatternNode,
            "true": LiteralPatternNode,
            '"ok"': LiteralPatternNode,
            "_": WildcardPatternNode,
        }
        for source, node_type in cases.items():
            with self.subTest(source=source):
                self.assertIsInstance(parse_pattern(source).pattern, node_type)

    def test_c_004_match_arm_mapping(self):
        program = parse(
            """
            module workflow {
                goal Done
                attribute state
                calculation Select {
                    match state {
                        Draft => approve()
                        Approved => publish()
                        _ => reject()
                    }
                    result = state
                }
            }
            """
        )
        calculation = program.modules[0].body[2]
        match = next(node for node in calculation.body if isinstance(node, MatchNode))
        self.assertIsInstance(match.arms[0].pattern.pattern, IdentifierPatternNode)
        self.assertIsInstance(match.arms[2].pattern.pattern, WildcardPatternNode)


if __name__ == "__main__":
    unittest.main()
