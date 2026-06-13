import dataclasses
import unittest

from operational_semantics_tests.reference_model import (
    ExecutionFailure,
    Goal,
    PlanningFailure,
    State,
    Transition,
    execute,
    goal_satisfied,
    plan,
    rollback,
)


class GoalAndStateSemantics(unittest.TestCase):
    def test_os_01_goal_is_terminal_pure_and_immutable(self):
        goal = Goal("reach_state", "Done")
        state = State("Done", "workflow")

        self.assertTrue(goal_satisfied(goal, state))
        self.assertEqual(goal, Goal("reach_state", "Done"))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            goal.target = "Changed"

    def test_os_02_state_snapshots_are_structurally_equal_and_immutable(self):
        left = State.from_mapping("Ready", "workflow", {"count": 1, "ok": True})
        right = State.from_mapping("Ready", "workflow", {"ok": True, "count": 1})

        self.assertEqual(left, right)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            left.state_id = "Changed"


class TransitionConstraintAndPlanningSemantics(unittest.TestCase):
    def setUp(self):
        self.initial = State("A", "symbolic")
        self.goal = Goal("reach_state", "D")
        self.transitions = (
            Transition("slow", "A", "D", 5.0),
            Transition("b", "A", "B", 1.0),
            Transition("d", "B", "D", 1.0),
            Transition("a", "A", "C", 1.0),
            Transition("c", "C", "D", 1.0),
        )

    def test_os_03_and_os_06_planning_uses_normative_selection_key(self):
        selected = plan(self.initial, self.goal, reversed(self.transitions))

        self.assertEqual(
            [step.transition_id for step in selected.selected_steps], ["a", "c"]
        )
        self.assertEqual(selected.expected_cost, 2.0)

    def test_os_04_constraint_is_evaluated_without_mutation(self):
        calls = []

        def reject_c(state, transition):
            calls.append((state, transition))
            return transition.target != "C"

        before = self.initial
        selected = plan(
            self.initial, self.goal, self.transitions, constraint=reject_c
        )

        self.assertEqual(self.initial, before)
        self.assertEqual(
            [step.transition_id for step in selected.selected_steps], ["b", "d"]
        )
        self.assertGreater(len(calls), 0)

    def test_os_06_zero_step_plan_and_bounded_failure(self):
        empty = plan(State("D", "symbolic"), self.goal, self.transitions)
        self.assertEqual(empty.selected_steps, ())

        with self.assertRaises(PlanningFailure):
            plan(self.initial, self.goal, self.transitions, max_depth=0)


class PlanDeltaAndResultSemantics(unittest.TestCase):
    def test_os_07_and_os_08_plan_order_delta_chain_and_rollback(self):
        initial = State("A", "symbolic")
        goal = Goal("reach_state", "C")
        transitions = (
            Transition("t1", "A", "B", 1.0),
            Transition("t2", "B", "C", 1.0),
        )
        selected = plan(initial, goal, transitions)
        final, deltas = execute(initial, goal, transitions, selected)

        self.assertEqual(final.state_id, "C")
        self.assertEqual(deltas[0].after_state, deltas[1].before_state)
        reverse = rollback(deltas[1], "delta-3")
        self.assertEqual(reverse.before_state, final)
        self.assertEqual(reverse.after_state.state_id, "B")
        self.assertEqual(reverse.applied_transition, "rollback:t2")

    def test_os_10_failed_validation_is_commit_free(self):
        initial = State("A", "symbolic")
        goal = Goal("reach_state", "B")
        transitions = (Transition("t1", "A", "B"),)
        selected = plan(initial, goal, transitions)

        with self.assertRaises(ExecutionFailure):
            execute(
                initial,
                goal,
                transitions,
                selected,
                constraint=lambda _state, _transition: False,
            )
        self.assertEqual(initial.state_id, "A")

    def test_os_10_tampered_plan_is_rejected(self):
        initial = State("A", "symbolic")
        goal = Goal("reach_state", "B")
        transitions = (Transition("t1", "A", "B"),)
        selected = plan(initial, goal, transitions)
        tampered_step = dataclasses.replace(selected.selected_steps[0], target="X")
        tampered = dataclasses.replace(selected, selected_steps=(tampered_step,))

        with self.assertRaises(ExecutionFailure):
            execute(initial, goal, transitions, tampered)


if __name__ == "__main__":
    unittest.main()
