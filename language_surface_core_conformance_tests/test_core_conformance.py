import json
import unittest

from conformance.framework import ROOT, validate_reason_ir
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    BinaryExpressionNode,
    CalculationNode,
    GoalStatementNode,
    IdentifierPatternNode,
    MatchStatementNode,
    RequireStatementNode,
    ResultStatementNode,
    SurfaceSyntaxError,
    Visibility,
    WildcardPatternNode,
    compile_program,
    execution_plan_for,
    from_json_value,
    parse,
    project_program,
    to_json_value,
)


SOURCE = """
pub module core {
    import common.finance as finance
    concept Person
    object User
    object Car
    object Engine
    event Rain
    event WetRoad
    action Approve
    attribute Age
    attribute income
    attribute factor
    attribute risk
    goal LoanApproval
    goal RiskEvaluation
    constraint Adult

    User IsA Person
    Engine PartOf Car
    Rain Cause WetRoad
    Age Dependency income
    Adult Constraint User
    Rain Temporal Approve
    User Spatial Car
    User Similar Person

    transition ApproveFlow {
        Draft -> Approved
        require Adult
        goal LoanApproval
        reach LoanApproval
        if Age >= 18 {
            publish(User)
        }
        else {
            reject(User)
        }
        match risk {
            High => review(User)
            _ => archive(User)
        }
    }

    pub calculation RiskScore goal:RiskEvaluation {
        let score = (income + 1) * factor
        score = score + 1
        normalize(score)
        match risk {
            High => result = score
            Low => result = 1
            _ => result = 0
        }
    }
}

module audit {
    event Login
    goal AuditComplete
}
"""


class LanguageSurfaceCoreConformanceTests(unittest.TestCase):
    def setUp(self):
        self.program = parse(SOURCE)
        self.frontend_schemas = SchemaValidator(ROOT / "frontend" / "schemas")
        self.schemas = SchemaValidator(ROOT / "schemas")

    def test_rc_001_module_declaration_and_relation_surface(self):
        core, audit = self.program.modules
        self.assertEqual(core.visibility, Visibility.PUBLIC)
        self.assertEqual(audit.visibility, Visibility.PRIVATE)
        self.assertEqual(core.body[0].path, ("common", "finance"))
        relations = [
            node.relation.value
            for node in core.body
            if type(node).__name__ == "RelationNode"
        ]
        self.assertEqual(
            relations,
            [
                "IsA",
                "PartOf",
                "Cause",
                "Dependency",
                "Constraint",
                "Temporal",
                "Spatial",
                "Similar",
            ],
        )

    def test_rc_002_statement_expression_and_pattern_surface(self):
        core = self.program.modules[0]
        transition = next(
            node for node in core.body if type(node).__name__ == "TransitionNode"
        )
        self.assertIsInstance(transition.body[0], RequireStatementNode)
        self.assertIsInstance(transition.body[1], GoalStatementNode)
        calculation = next(
            node for node in core.body if isinstance(node, CalculationNode)
        )
        expression = calculation.body[0].expression.expression
        self.assertIsInstance(expression, BinaryExpressionNode)
        match = next(
            node for node in calculation.body if isinstance(node, MatchStatementNode)
        )
        self.assertIsInstance(match.arms[0].pattern.pattern, IdentifierPatternNode)
        self.assertIsInstance(match.arms[-1].pattern.pattern, WildcardPatternNode)
        self.assertIsInstance(match.arms[0].body[-1], ResultStatementNode)

    def test_rc_003_surface_ast_schema_and_round_trip(self):
        value = to_json_value(self.program)
        self.assertEqual(json.loads(json.dumps(value)), value)
        self.frontend_schemas.validate_file(
            value, "language_surface_ast.schema.json"
        )
        self.assertEqual(from_json_value(value), self.program)
        self.assertTrue(_all_nodes_tagged(value))

    def test_rc_004_semantic_ast_and_deterministic_replay(self):
        first = project_program(self.program)
        second = project_program(parse(SOURCE))
        self.assertEqual(first, second)
        self.assertEqual(compile_program(self.program), compile_program(parse(SOURCE)))

    def test_rc_005_reason_ir_compatibility(self):
        for reason_ir in compile_program(self.program):
            validate_reason_ir(reason_ir)
            self.schemas.validate_file(reason_ir, "reason_ir.schema.json")
            self.assertEqual(reason_ir["schema_version"], "reason-ir/0.1")

    def test_rc_006_execution_plan_compatibility_and_order(self):
        reason_ir = compile_program(self.program)[0]
        plan = execution_plan_for(reason_ir)
        self.schemas.validate_file(plan, "execution_plan.schema.json")
        self.assertEqual(
            [step["transition_id"] for step in plan["selected_steps"]],
            [transition["transition_id"] for transition in reason_ir["transitions"]],
        )
        calculation_relations = [
            transition["relation"]
            for transition in reason_ir["transitions"]
            if transition["transition_id"].startswith("RiskScore-")
        ]
        self.assertEqual(
            calculation_relations,
            [
                "MultiplyTransition",
                "StateUpdateTransition",
                "CallTransition",
                "DecisionTransition",
            ],
        )

    def test_rc_007_reference_and_scope_failures_are_pre_compilation(self):
        invalid_sources = (
            (
                "AST-V004",
                "module invalid {\nconcept User\nUser IsA Missing\n}",
            ),
            (
                "ST-030",
                "module invalid {\nconstraint Adult\ntransition T {\n"
                "A -> B\nrequire Missing\n}\n}",
            ),
            (
                "CAL-020",
                "module invalid {\ncalculation C {\nresult = missing\n}\n}",
            ),
            (
                "CAL-V008",
                "module invalid {\ncalculation C goal:Missing {\nresult = 1\n}\n}",
            ),
        )
        for code, source in invalid_sources:
            with self.subTest(code=code), self.assertRaisesRegex(
                SurfaceSyntaxError, code
            ):
                parse(source)

    def test_rc_008_interface_versions_remain_fixed(self):
        semantic = project_program(self.program)
        self.assertTrue(
            all(module.version == "reasonscript-ast/0.1" for module in semantic)
        )
        reason_ir = compile_program(self.program)[0]
        plan = execution_plan_for(reason_ir)
        self.assertEqual(reason_ir["schema_version"], "reason-ir/0.1")
        self.assertEqual(
            plan["planner_version"], "language-surface-validation/0.1"
        )


def _all_nodes_tagged(value):
    if isinstance(value, dict):
        if "node_type" not in value:
            return False
        return all(
            _all_nodes_tagged(item)
            for key, item in value.items()
            if key != "node_type"
        )
    if isinstance(value, list):
        return all(_all_nodes_tagged(item) for item in value)
    return True


if __name__ == "__main__":
    unittest.main()
