import json
import unittest

from conformance.framework import execute_reason_ir, validate_reason_ir
from conformance.schema_validator import SchemaValidator
from frontend.ast import (
    AstValidationError,
    ConstraintNode,
    ContextNode,
    GoalNode,
    MappingOptions,
    MetadataNode,
    ModuleNode,
    StateNode,
    TransitionNode,
    to_json_value,
    to_reason_ir,
    validate,
)
from conformance.framework import ROOT


def module_for(*declarations, metadata=()):
    return ModuleNode(
        node_id="module",
        declarations=tuple(declarations),
        metadata=tuple(metadata),
    )


class AstValidationCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = SchemaValidator(ROOT / "schemas")

    def assert_lowers(self, module):
        value = to_reason_ir(module)
        self.schema.validate_file(value, "reason_ir.schema.json")
        validate_reason_ir(value)
        return value

    def test_case_1_basic_inference(self):
        value = self.assert_lowers(
            module_for(
                GoalNode("goal", "reach_state", "Animal"),
                StateNode("state", "Dog", "symbolic", {"label": "dog"}),
                TransitionNode("t1-node", "dog-is-mammal", "Dog", "IsA", "Mammal"),
                TransitionNode(
                    "t2-node", "mammal-is-animal", "Mammal", "IsA", "Animal"
                ),
            )
        )
        self.assertEqual(execute_reason_ir(value)["status"], "completed")

    def test_case_2_constraint(self):
        value = self.assert_lowers(
            module_for(
                GoalNode("goal", "reach_state", "Adult"),
                StateNode("state", "Person", "entity", {"age": 20}),
                ConstraintNode("constraint", "adult-only", "predicate", "age >= 18"),
                TransitionNode("transition", "become-adult", "Person", "IsA", "Adult"),
            )
        )
        self.assertEqual(value["constraints"][0]["constraint_id"], "adult-only")

    def test_case_3_context_reference(self):
        value = self.assert_lowers(
            module_for(
                GoalNode("goal", "produce_answer", "Known"),
                StateNode("state", "Unknown", "query", {}),
                ContextNode(
                    "context", "knowledge-base", "database", "db://knowledge/main"
                ),
            )
        )
        self.assertEqual(value["context_refs"][0]["context_type"], "database")

    def test_case_4_tool_integration(self):
        value = self.assert_lowers(
            module_for(
                GoalNode("goal", "produce_answer", "WeatherAnswer"),
                StateNode(
                    "state", "WeatherQuery", "tool_request", {"city": "Tokyo"}
                ),
                ContextNode(
                    "context", "weather-tool", "tool", "tool://weather.lookup"
                ),
                TransitionNode(
                    "transition",
                    "invoke-weather",
                    "WeatherQuery",
                    "InvokeTool",
                    "WeatherAnswer",
                    effect={"tool_ref": "weather.lookup"},
                ),
            )
        )
        self.assertEqual(value["transitions"][0]["relation"], "InvokeTool")

    def test_case_5_world_model_transition(self):
        value = self.assert_lowers(
            module_for(
                GoalNode("goal", "reach_state", "RoomLit"),
                StateNode("state", "RoomDark", "world_model", {"light": "off"}),
                TransitionNode(
                    "transition",
                    "switch-light-on",
                    "RoomDark",
                    "Action",
                    "RoomLit",
                    expected_cost=0.1,
                    effect={"light": "on"},
                ),
            )
        )
        self.assertEqual(execute_reason_ir(value)["final_state_id"], "RoomLit")

    def test_case_6_dbm_planning(self):
        value = to_reason_ir(
            module_for(
                GoalNode("goal", "reach_state", "PlanComplete"),
                StateNode("state", "PlanStart", "dbm", {"budget": 10}),
                ConstraintNode(
                    "constraint", "within-budget", "numeric", "budget >= 5"
                ),
                TransitionNode(
                    "transition", "select-plan", "PlanStart", "Plan", "PlanComplete"
                ),
            ),
            MappingOptions(
                planner_policy={
                    "strategy": "minimum_expected_cost",
                    "max_depth": 16,
                    "max_alternatives": 4,
                }
            ),
        )
        validate_reason_ir(value)
        self.assertEqual(value["planner_policy"]["max_depth"], 16)


class AstInvariantTests(unittest.TestCase):
    def test_ast_is_json_representable(self):
        value = to_json_value(
            module_for(
                GoalNode("goal", "reach_state", "B"),
                StateNode("state", "A", "symbolic", {}),
                metadata=(MetadataNode("metadata", "producer", "test"),),
            )
        )
        self.assertEqual(json.loads(json.dumps(value)), value)

    def test_node_ids_are_unique(self):
        value = module_for(
            GoalNode("same", "reach_state", "B"),
            StateNode("same", "A", "symbolic", {}),
        )
        with self.assertRaisesRegex(AstValidationError, "duplicate node_id"):
            validate(value)

    def test_exactly_one_goal_and_initial_state_are_required(self):
        with self.assertRaisesRegex(AstValidationError, "GoalNode"):
            validate(module_for(StateNode("state", "A", "symbolic", {})))
        with self.assertRaisesRegex(AstValidationError, "initial StateNode"):
            validate(
                module_for(
                    GoalNode("goal", "reach_state", "B"),
                    StateNode("state-a", "A", "symbolic", {}),
                    StateNode("state-b", "B", "symbolic", {}),
                )
            )

    def test_duplicate_reason_ir_ids_are_rejected(self):
        value = module_for(
            GoalNode("goal", "reach_state", "C"),
            StateNode("state", "A", "symbolic", {}),
            TransitionNode("node-1", "duplicate", "A", "IsA", "B"),
            TransitionNode("node-2", "duplicate", "B", "IsA", "C"),
        )
        with self.assertRaisesRegex(AstValidationError, "duplicate transition_id"):
            validate(value)

    def test_runtime_objects_and_non_finite_numbers_are_rejected(self):
        value = module_for(
            GoalNode("goal", "reach_state", "B"),
            StateNode("state", "A", "symbolic", {"bad": object()}),
        )
        with self.assertRaisesRegex(AstValidationError, "not JSON-compatible"):
            validate(value)
        bad_cost = module_for(
            GoalNode("goal", "reach_state", "B"),
            StateNode("state", "A", "symbolic", {}),
            TransitionNode("transition", "t1", "A", "IsA", "B", float("inf")),
        )
        with self.assertRaisesRegex(AstValidationError, "finite"):
            validate(bad_cost)

    def test_mapping_is_deterministic_and_does_not_import_runtime_or_sdk(self):
        module = module_for(
            GoalNode("goal", "reach_state", "B"),
            StateNode("state", "A", "symbolic", {}),
        )
        self.assertEqual(to_reason_ir(module), to_reason_ir(module))
        source = (ROOT / "frontend" / "ast" / "mapping.py").read_text()
        self.assertNotIn("HybridRuntime", source)
        self.assertNotIn("RuntimeReal", source)
        self.assertNotIn("reasonscript_dto", source)


if __name__ == "__main__":
    unittest.main()
