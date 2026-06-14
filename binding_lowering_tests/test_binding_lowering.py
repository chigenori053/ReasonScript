import dataclasses
import unittest

from calculation_semantics_tests.model import lower_program, parse_calculations


class BindingLoweringTests(unittest.TestCase):
    def test_cs_01_binding_ids_and_state_entries_are_deterministic(self):
        source = """
        pub calculation Example goal:value {
            let x = 10
            result = x
        }
        """
        first = lower_program(parse_calculations(source))
        second = lower_program(parse_calculations(source))
        binding = first.calculations[0].bindings[0]
        self.assertEqual(binding.binding_id, "Example.binding.x")
        self.assertEqual(binding.value, 10)
        self.assertEqual(first, second)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            binding.value = 11


if __name__ == "__main__":
    unittest.main()
