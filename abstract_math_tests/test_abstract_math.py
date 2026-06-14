import unittest

from computation_model_tests.model import MathState, MathTransition, run_procedure


class AbstractMathematicsValidation(unittest.TestCase):
    def test_graph_traversal_is_a_state_progression(self):
        graph = {"A": ["B", "C"], "B": ["D"], "C": [], "D": []}
        rules = (
            MathTransition(
                "visit-a",
                "QueueA",
                "QueueBC",
                "GraphTraversal",
                lambda d: {"graph": d["graph"], "visited": ["A"], "queue": ["B", "C"]},
            ),
            MathTransition(
                "visit-b",
                "QueueBC",
                "QueueCD",
                "GraphTraversal",
                lambda d: {"graph": d["graph"], "visited": d["visited"] + ["B"], "queue": ["C", "D"]},
            ),
            MathTransition(
                "visit-cd",
                "QueueCD",
                "Solved",
                "GraphTraversal",
                lambda d: {"visited": d["visited"] + ["C", "D"], "queue": []},
            ),
        )
        _, result = run_procedure(MathState.create("QueueA", {"graph": graph}), "Solved", rules)
        self.assertEqual(result.final_state.data["visited"], ["A", "B", "C", "D"])

    def test_formal_logic_proof_is_an_execution_plan(self):
        rules = (
            MathTransition(
                "modus-ponens",
                "Premises",
                "DerivedQ",
                "LogicalInference",
                lambda d: {"facts": d["facts"] + ["Q"]},
            ),
            MathTransition(
                "modus-ponens-2",
                "DerivedQ",
                "Solved",
                "LogicalInference",
                lambda d: {"facts": d["facts"] + ["R"], "theorem": "R"},
            ),
        )
        plan, result = run_procedure(
            MathState.create("Premises", {"facts": ["P", "P->Q", "Q->R"]}),
            "Solved",
            rules,
        )
        self.assertEqual(result.final_state.data["theorem"], "R")
        self.assertEqual(result.proof_step_ids, tuple(step.step_id for step in plan.selected_steps))

    def test_set_operations(self):
        rule = MathTransition(
            "set-union-intersection",
            "Sets",
            "Solved",
            "SetOperation",
            lambda d: {
                "union": sorted(set(d["left"]) | set(d["right"])),
                "intersection": sorted(set(d["left"]) & set(d["right"])),
            },
        )
        _, result = run_procedure(
            MathState.create("Sets", {"left": [1, 2], "right": [2, 3]}),
            "Solved",
            (rule,),
        )
        self.assertEqual(result.final_state.data, {"intersection": [2], "union": [1, 2, 3]})

    def test_group_closure(self):
        rule = MathTransition(
            "close-z3",
            "Generators",
            "Solved",
            "GroupClosure",
            lambda d: {
                "elements": sorted({(a + b) % 3 for a in d["seed"] for b in range(3)}),
                "operation": "addition mod 3",
            },
        )
        _, result = run_procedure(MathState.create("Generators", {"seed": [1]}), "Solved", (rule,))
        self.assertEqual(result.final_state.data["elements"], [0, 1, 2])

    def test_ring_distributivity(self):
        rule = MathTransition(
            "verify-distributivity",
            "RingExpression",
            "Solved",
            "RingLaw",
            lambda d: {
                "left": d["a"] * (d["b"] + d["c"]),
                "right": d["a"] * d["b"] + d["a"] * d["c"],
            },
        )
        _, result = run_procedure(
            MathState.create("RingExpression", {"a": 2, "b": 3, "c": 4}),
            "Solved",
            (rule,),
        )
        self.assertEqual(result.final_state.data["left"], result.final_state.data["right"])

    def test_category_composition(self):
        rules = (
            MathTransition(
                "apply-f",
                "ObjectA",
                "ObjectB",
                "Morphism",
                lambda d: {"value": d["value"] + 1, "morphism": "f"},
            ),
            MathTransition(
                "apply-g",
                "ObjectB",
                "Solved",
                "Morphism",
                lambda d: {"value": d["value"] * 2, "morphism": "g o f"},
            ),
        )
        _, result = run_procedure(MathState.create("ObjectA", {"value": 3}), "Solved", rules)
        self.assertEqual(result.final_state.data, {"morphism": "g o f", "value": 8})


if __name__ == "__main__":
    unittest.main()
