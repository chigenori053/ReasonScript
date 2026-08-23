import unittest

from frontend.computation_ir import lower_program, validate_program
from frontend.language_surface import parse


class ComputationIrValidationTests(unittest.TestCase):
    def test_lowered_program_with_loops_and_calls_is_well_formed(self):
        program = parse(
            """module M {
  fn square(x) {
    return x * x
  }
  calculation Answer {
    let values = [1, 2, 3, 4]
    let total = 0
    for v in values {
      total = total + square(v)
    }
    result = total
  }
}
"""
        )
        ir = lower_program(program)
        self.assertEqual(validate_program(ir), [])

    def test_unknown_schema_is_rejected(self):
        errors = validate_program({"schema": "not-the-right-schema/9.9", "functions": [], "calculations": []})
        self.assertTrue(any("unexpected schema" in error for error in errors))

    def test_dangling_jump_target_is_rejected(self):
        program = parse(
            """module M {
  calculation Answer {
    result = 1
  }
}
"""
        )
        ir = lower_program(program)
        ir["functions"][0]["blocks"][0]["terminator"] = {"kind": "jump", "target": "does-not-exist"}
        errors = validate_program(ir)
        self.assertTrue(any("unknown" in error for error in errors))

    def test_unreachable_block_is_reported(self):
        program = parse(
            """module M {
  calculation Answer {
    let x = 1
    if x == 1 {
      x = 2
    } else {
      x = 3
    }
    result = x
  }
}
"""
        )
        ir = lower_program(program)
        function = ir["functions"][0]
        # Add a block nothing points to.
        function["blocks"].append({
            "id": "orphan",
            "instructions": [],
            "terminator": {"kind": "result", "value": {"op": "const", "kind": "int", "value": 0}},
        })
        errors = validate_program(ir)
        self.assertTrue(any("unreachable" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
