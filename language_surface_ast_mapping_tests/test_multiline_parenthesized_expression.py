import unittest

from frontend.language_surface import parse, ParenthesizedExpressionNode, LetStatementNode, SurfaceSyntaxError


class MultiLineParenthesizedExpressionTests(unittest.TestCase):
    def test_multiline_parenthesized_expression_parses(self):
        source = """
        module m {
            fn f() {
                let x = (
                    1
                    + 2
                )
                return x
            }
        }
        """
        program = parse(source)
        # find the let statement and ensure its expression is parenthesized
        module = program.modules[0]
        let_nodes = [n for n in module.body[0].body if isinstance(n, LetStatementNode)]
        self.assertTrue(len(let_nodes) >= 1)
        expr = let_nodes[0].expression
        self.assertIsInstance(expr.expression, ParenthesizedExpressionNode)

    def test_nested_parenthesized_expression_parses(self):
        source = """
        module m {
            fn f() {
                let y = (
                    (1 + 2)
                    + 3
                )
                return y
            }
        }
        """
        program = parse(source)
        module = program.modules[0]
        let_nodes = [n for n in module.body[0].body if isinstance(n, LetStatementNode)]
        self.assertTrue(len(let_nodes) >= 1)
        expr = let_nodes[0].expression
        self.assertIsInstance(expr.expression, ParenthesizedExpressionNode)

    def test_unterminated_parenthesized_expression_raises(self):
        source = """
        module m {
            fn f() {
                let z = (
                    1 + 2
                
                return z
            }
        }
        """
        with self.assertRaises(SurfaceSyntaxError):
            parse(source)


if __name__ == "__main__":
    unittest.main()
