import unittest

from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    OptionalTypeNode,
    RuntimeCallExpressionNode,
    RuntimeCallKind,
    SurfaceSyntaxError,
    compile_program,
    from_json_value,
    parse,
    to_json_value,
)


class PlatformPhase8RuntimeNamespaceTests(unittest.TestCase):
    def test_runtime_calls_are_ast_nodes_optional_and_metadata(self):
        program = parse(
            """
            package world

            module runtime_client {
                fn use_runtime(goal) {
                    let search_result: optional<SearchResult> = runtime.search(goal)
                    let simulation = runtime.simulate(search_result)
                    let prediction = runtime.predict(goal)
                    let plan = runtime.plan(goal)
                    match search_result {
                        some(result) => return result
                        none => return plan
                    }
                }
            }
            """
        )

        function = program.modules[0].body[0]
        search_statement = function.body[0]
        runtime_call = search_statement.expression.expression
        self.assertIsInstance(runtime_call, RuntimeCallExpressionNode)
        self.assertEqual(runtime_call.method, "search")
        self.assertEqual(runtime_call.kind, RuntimeCallKind.SEARCH)
        self.assertIsInstance(search_statement.type_annotation, OptionalTypeNode)

        value = to_json_value(program)
        SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
            value, "language_surface_ast.schema.json"
        )
        self.assertEqual(from_json_value(value), program)

        reason_ir = compile_program(program)[0]
        metadata = reason_ir["metadata"]
        self.assertEqual(
            metadata["runtime_calls"],
            ["search", "simulate", "predict", "plan"],
        )
        self.assertEqual(
            [item["node_type"] for item in metadata["runtime_operations"]],
            [
                "RuntimeSearchNode",
                "RuntimeSimulateNode",
                "RuntimePredictNode",
                "RuntimePlanNode",
            ],
        )

    def test_runtime_namespace_validation_errors(self):
        cases = (
            (
                "RuntimeNamespaceCannotBeImported",
                """
                package world
                module app {
                    import runtime.search
                }
                """,
            ),
            (
                "ReservedRuntimeNamespace",
                """
                package runtime
                module app {
                }
                """,
            ),
            (
                "reserved keyword: runtime",
                """
                package world
                module app {
                    struct runtime {
                    }
                }
                """,
            ),
            (
                "UnknownRuntimeMethod",
                """
                package world
                module app {
                    fn bad(goal) {
                        return runtime.unknown(goal)
                    }
                }
                """,
            ),
            (
                "RuntimeCallArgumentCountMismatch",
                """
                package world
                module app {
                    fn bad(goal) {
                        return runtime.search(goal, goal)
                    }
                }
                """,
            ),
            (
                "reserved keyword: runtime",
                """
                package world
                module app {
                    fn bad(goal) {
                        let runtime = goal
                        return runtime
                    }
                }
                """,
            ),
        )
        for code, source in cases:
            with self.subTest(code=code), self.assertRaisesRegex(
                SurfaceSyntaxError, code
            ):
                parse(source)


if __name__ == "__main__":
    unittest.main()
