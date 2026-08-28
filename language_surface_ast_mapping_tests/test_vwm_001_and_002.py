import unittest

from frontend.language_surface import parse, project_program

# RS-VWM-001 reproduction: nested call into branching function should not produce duplicate transition ids
RS_VWM_001 = '''
module NestedOuterBranch {
 fn Inner(value: int) -> int {
 return value + 1
 }

 fn Outer(value: int) -> int {
 if value > 0 {
 return 2
 }
 return 0
 }

 calculation Probe {
 result = Outer(Inner(1))
 }
}
'''

# RS-VWM-002 reproduction: multiline function parameter declaration
RS_VWM_002 = '''
module MultilineSignature {
 fn Add(
 left: int,
 right: int
 ) -> int {
 return left + right
 }

 calculation Probe {
 result = Add(1, 2)
 }
}
'''

class VWMTests(unittest.TestCase):
    def test_rs_vwm_001_no_duplicate_transition_id(self):
        program = parse(RS_VWM_001)
        # project_program should not raise an error related to duplicate transition ids
        modules = project_program(program)
        self.assertTrue(len(modules) >= 1)

    def test_rs_vwm_002_multiline_signature_parses(self):
        program = parse(RS_VWM_002)
        modules = project_program(program)
        self.assertTrue(len(modules) >= 1)


if __name__ == "__main__":
    unittest.main()
