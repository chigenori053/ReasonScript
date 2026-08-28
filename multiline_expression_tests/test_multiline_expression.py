from frontend.language_surface import parse
from frontend.language_surface.nodes import LetStatementNode


def test_parenthesized_multiline_expression_is_one_logical_statement():
    program = parse("""
    module sample {
        calculation Main {
            let x = (
                1
                + 2
                + 3
            )
            result = x
        }
    }
    """)
    statement = program.modules[0].body[0].body[0]
    assert isinstance(statement, LetStatementNode)
