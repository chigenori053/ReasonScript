import unittest

from frontend.compiler import CompilationPolicies, CompilerError, CompilerErrorCode
from frontend.compiler.injector import inject_policies


class CompilerPolicyTests(unittest.TestCase):
    def test_default_policies_match_contract(self):
        context = inject_policies()
        self.assertEqual(
            context.execution_policy,
            {
                "max_steps": 128,
                "rollback_on_failure": True,
                "constraint_mode": "reject",
            },
        )
        self.assertEqual(
            context.trace_policy,
            {
                "level": "standard",
                "include_alternatives": True,
                "include_state_data": True,
            },
        )
        self.assertEqual(
            context.planner_policy,
            {
                "strategy": "minimum_expected_cost",
                "max_depth": 128,
                "max_alternatives": 8,
            },
        )

    def test_valid_override_is_preserved(self):
        policies = CompilationPolicies(
            execution_policy={
                "max_steps": 4,
                "rollback_on_failure": False,
                "constraint_mode": "report",
            },
            trace_policy={
                "level": "minimal",
                "include_alternatives": False,
                "include_state_data": False,
            },
            planner_policy=None,
        )
        context = inject_policies(policies)
        self.assertEqual(context.execution_policy["max_steps"], 4)
        self.assertIsNone(context.planner_policy)

    def test_invalid_policy_returns_specific_error(self):
        policies = CompilationPolicies(
            execution_policy={
                "max_steps": 0,
                "rollback_on_failure": True,
                "constraint_mode": "reject",
            }
        )
        with self.assertRaises(CompilerError) as raised:
            inject_policies(policies)
        self.assertEqual(raised.exception.code, CompilerErrorCode.INVALID_POLICY)


if __name__ == "__main__":
    unittest.main()
