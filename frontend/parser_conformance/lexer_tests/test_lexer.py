import unittest

from frontend.parser import TokenType, tokenize
from frontend.parser_conformance.framework import VALID_FIXTURES, load_source


class LexerConformanceTests(unittest.TestCase):
    def test_contract_token_categories(self):
        tokens = tokenize(
            'goal "Animal"\nstate Dog\ncontext memory://animals\n'
            "transition Dog IsA Animal\nconstraint Rule\nimport lib.core\n42\n"
        )
        categories = {token.token_type for token in tokens}
        self.assertEqual(
            categories,
            {
                TokenType.KEYWORD,
                TokenType.IDENTIFIER,
                TokenType.STRING,
                TokenType.NUMBER,
                TokenType.URI,
                TokenType.NEWLINE,
                TokenType.EOF,
            },
        )

    def test_positions_and_utf8_identifiers(self):
        tokens = tokenize("goal 動物\nstate 犬")
        self.assertEqual((tokens[1].value, tokens[1].line, tokens[1].column), ("動物", 1, 6))
        self.assertEqual((tokens[4].value, tokens[4].line, tokens[4].column), ("犬", 2, 7))

    def test_fixture_tokenization_is_deterministic(self):
        for path in sorted(VALID_FIXTURES.glob("*.rsn")):
            source = load_source(path)
            self.assertEqual(tokenize(source), tokenize(source), path.name)


if __name__ == "__main__":
    unittest.main()
