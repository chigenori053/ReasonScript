import unittest

from frontend.language_surface import SurfaceSyntaxError, parse


class LayerCReferenceResolutionTests(unittest.TestCase):
    def test_c_001_and_c_002_goal_and_constraint_exist(self):
        parse(
            """
            module valid {
                constraint Adult
                goal Approved
                transition Go {
                    Start -> Finish
                    require Adult
                    goal Approved
                    reach Approved
                }
            }
            """
        )

    def test_c_003_goal_type_must_match(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "ST-041"):
            parse(
                """
                module invalid {
                    action Approved
                    transition Go {
                        Start -> Finish
                        goal Approved
                    }
                }
                """
            )

    def test_c_004_constraint_type_must_match(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "ST-031"):
            parse(
                """
                module invalid {
                    action Adult
                    transition Go {
                        Start -> Finish
                        require Adult
                    }
                }
                """
            )

    def test_missing_goal_and_constraint_are_rejected(self):
        for statement, code in (("goal Missing", "ST-040"), ("require Missing", "ST-030")):
            with self.subTest(statement=statement), self.assertRaisesRegex(
                SurfaceSyntaxError, code
            ):
                parse(
                    f"""
                    module invalid {{
                        transition Go {{
                            Start -> Finish
                            {statement}
                        }}
                    }}
                    """
                )


if __name__ == "__main__":
    unittest.main()
