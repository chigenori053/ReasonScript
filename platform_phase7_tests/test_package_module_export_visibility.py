import unittest

from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    ConstDeclarationNode,
    FunctionDeclarationNode,
    PackageDeclarationNode,
    StructDeclarationNode,
    SurfaceSyntaxError,
    Visibility,
    compile_program,
    from_json_value,
    parse,
    project_program,
    to_json_value,
)


class PlatformPhase7PackageModuleTests(unittest.TestCase):
    def test_package_export_import_alias_metadata_and_round_trip(self):
        program = parse(
            """
            package world

            module search {
                export const VERSION = "1.0"
                export struct Result {
                    label: string
                }
                export fn find() {
                    return VERSION
                }
                fn helper() {
                    return VERSION
                }
            }

            module app {
                import world.search as search
                fn use_search() {
                    return search.find()
                }
            }

            module direct {
                fn use_search() {
                    return world.search.find()
                }
            }
            """
        )

        self.assertEqual(program.package, PackageDeclarationNode("world"))
        search = program.modules[0]
        self.assertIsInstance(search.body[0], ConstDeclarationNode)
        self.assertEqual(search.body[0].visibility, Visibility.PUBLIC)
        self.assertIsInstance(search.body[1], StructDeclarationNode)
        self.assertEqual(search.body[1].visibility, Visibility.PUBLIC)
        self.assertIsInstance(search.body[2], FunctionDeclarationNode)
        self.assertEqual(search.body[2].visibility, Visibility.PUBLIC)
        self.assertEqual(search.body[3].visibility, Visibility.PRIVATE)

        value = to_json_value(program)
        SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
            value, "language_surface_ast.schema.json"
        )
        self.assertEqual(from_json_value(value), program)

        semantic = project_program(program)[0]
        metadata = {item.key: item.value for item in semantic.metadata}
        self.assertEqual(metadata["package"], "world")
        self.assertEqual(metadata["module"], "search")
        self.assertEqual(metadata["namespace"], "world.search")
        self.assertEqual(metadata["exports"], ["VERSION", "Result", "find"])

        reason_ir = compile_program(program)[0]
        self.assertEqual(reason_ir["metadata"]["package"], "world")
        self.assertEqual(reason_ir["metadata"]["module"], "search")
        self.assertEqual(reason_ir["metadata"]["exports"], ["VERSION", "Result", "find"])

    def test_private_symbol_is_not_visible_outside_module(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "private symbol"):
            parse(
                """
                package world

                module search {
                    export const VERSION = "1.0"
                    fn helper() {
                        return 1
                    }
                }

                module app {
                    import world.search
                    fn use_helper() {
                        return search.helper()
                    }
                }
                """
            )

    def test_phase7_validation_errors(self):
        cases = (
            (
                "PackageMustAppearFirst",
                """
                module search {
                }
                package world
                """,
            ),
            (
                "ModuleNotFound",
                """
                package world
                module search {
                    import world.scene
                }
                """,
            ),
            (
                "CircularImport",
                """
                package world
                module a {
                    import world.b
                }
                module b {
                    import world.a
                }
                """,
            ),
            (
                "UnsupportedFeature",
                """
                package world
                module search {
                    export import world.scene
                }
                """,
            ),
            (
                "ExportMustBeTopLevel",
                """
                package world
                module search {
                    fn bad() {
                        export fn inner() {
                            return 1
                        }
                    }
                }
                """,
            ),
            (
                "duplicate symbol",
                """
                package world
                module search {
                    export fn find() {
                        return 1
                    }
                    export struct find {
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
