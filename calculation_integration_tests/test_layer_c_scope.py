import unittest

from frontend.language_surface import SurfaceSyntaxError, parse


class LayerCScopeTests(unittest.TestCase):
    def test_c_001_variable_resolution(self):
        parse(
            """
            module scope {
                attribute income
                calculation Risk {
                    let score = income * 2
                    score = score + 1
                    result = score
                }
            }
            """
        )

    def test_c_002_duplicate_binding(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CAL-021"):
            parse(
                """
                module scope {
                    calculation Risk {
                        let score = 1
                        let score = 2
                        result = score
                    }
                }
                """
            )

    def test_c_003_undefined_variable(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CAL-020"):
            parse(
                """
                module scope {
                    calculation Risk {
                        result = missing
                    }
                }
                """
            )


if __name__ == "__main__":
    unittest.main()
