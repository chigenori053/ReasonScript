"""Tests for static Call Graph Analysis in ReasonScript."""

import unittest

from frontend.language_surface import analyze_call_graph, parse


class CallGraphAnalysisTests(unittest.TestCase):
    def test_non_recursive_dag(self):
        source = """module M {
  fn helper(x: Int): Int {
    return x + 1
  }

  fn main_func(x: Int): Int {
    return helper(x) * 2
  }

  calculation Calc {
    let v = main_func(10)
    result = v
  }
}
"""
        program = parse(source)
        cg = analyze_call_graph(program)

        self.assertIn("helper", cg.functions)
        self.assertIn("main_func", cg.functions)
        self.assertIn("Calc", cg.calculations)

        self.assertEqual(cg.callees["main_func"], {"helper"})
        self.assertEqual(cg.callees["helper"], set())
        self.assertEqual(cg.callees["Calc"], {"main_func"})
        self.assertEqual(cg.callers["helper"], {"main_func"})
        self.assertEqual(cg.callers["main_func"], {"Calc"})

        self.assertFalse(cg.is_recursive("helper"))
        self.assertFalse(cg.is_recursive("main_func"))
        self.assertIsNone(cg.recursion_kind("helper"))
        self.assertIsNone(cg.recursion_kind("main_func"))
        self.assertEqual(cg.cycles, [])

    def test_direct_recursion(self):
        source = """module M {
  fn factorial(n: Int): Int {
    if n <= 1 {
      return 1
    }
    return n * factorial(n - 1)
  }

  calculation Calc {
    result = factorial(5)
  }
}
"""
        program = parse(source)
        cg = analyze_call_graph(program)

        self.assertTrue(cg.is_recursive("factorial"))
        self.assertEqual(cg.recursion_kind("factorial"), "direct")
        self.assertIn("factorial", cg.direct_recursive)
        self.assertNotIn("factorial", cg.mutual_recursive)

    def test_mutual_recursion(self):
        source = """module M {
  fn is_even(n: Int): Bool {
    if n == 0 {
      return true
    }
    return is_odd(n - 1)
  }

  fn is_odd(n: Int): Bool {
    if n == 0 {
      return false
    }
    return is_even(n - 1)
  }

  calculation Calc {
    result = is_even(4)
  }
}
"""
        program = parse(source)
        cg = analyze_call_graph(program)

        self.assertTrue(cg.is_recursive("is_even"))
        self.assertTrue(cg.is_recursive("is_odd"))
        self.assertEqual(cg.recursion_kind("is_even"), "mutual")
        self.assertEqual(cg.recursion_kind("is_odd"), "mutual")
        self.assertEqual(cg.mutual_recursive, {"is_even", "is_odd"})
        self.assertEqual(len(cg.cycles), 1)

    def test_complex_mixed_graph(self):
        source = """module M {
  fn a(x: Int): Int {
    return b(x)
  }

  fn b(x: Int): Int {
    return c(x)
  }

  fn c(x: Int): Int {
    return a(x)
  }

  fn self_rec(x: Int): Int {
    return self_rec(x)
  }

  fn leaf(x: Int): Int {
    return x
  }
}
"""
        program = parse(source)
        cg = analyze_call_graph(program)

        self.assertEqual(cg.recursion_kind("self_rec"), "direct")
        self.assertEqual(cg.recursion_kind("a"), "mutual")
        self.assertEqual(cg.recursion_kind("b"), "mutual")
        self.assertEqual(cg.recursion_kind("c"), "mutual")
        self.assertIsNone(cg.recursion_kind("leaf"))

        data = cg.to_dict()
        self.assertIn("functions", data)
        self.assertIn("cycles", data)


if __name__ == "__main__":
    unittest.main()
