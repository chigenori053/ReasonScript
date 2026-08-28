import unittest

from frontend.language_surface import parse
from frontend.language_surface.integration import compile_program
from toolchain.code_viewer.projection import _transition_symbol_map

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

class TransitionSymbolMapTests(unittest.TestCase):
    def test_transition_symbol_map_contains_unique_function_return_ids(self):
        program = parse(RS_VWM_001)
        reason_irs = compile_program(program)
        self.assertTrue(reason_irs)
        ir = reason_irs[0]
        # Build the transition symbol map used by CodeViewer
        symbol_map = _transition_symbol_map(ir)
        # Ensure all transitions with an effect.calculation map to that calculation
        seen_ids = set()
        for t in ir.get("transitions", []):
            tid = t.get("transition_id")
            effect = t.get("effect")
            if isinstance(effect, dict) and "calculation" in effect:
                self.assertIn(tid, symbol_map, msg=f"transition_id {tid} missing from symbol map")
                self.assertEqual(symbol_map[tid], effect["calculation"])
            # ensure unique ids
            self.assertNotIn(tid, seen_ids, msg=f"duplicate transition_id in IR: {tid}")
            seen_ids.add(tid)


if __name__ == "__main__":
    unittest.main()
