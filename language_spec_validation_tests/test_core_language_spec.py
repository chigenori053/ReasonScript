import unittest

from frontend.ast import (
    ConstraintNode,
    ContextNode,
    GoalNode,
    MetadataNode,
    ModuleNode,
    StateNode,
    TransitionNode,
    to_reason_ir,
)
from frontend.language import (
    ImportCycleError,
    ModuleResolutionError,
    SymbolKind,
    UnknownModuleError,
    UnknownSymbolError,
    resolve_modules,
)


def module(name, *declarations, imports=(), metadata=()):
    return ModuleNode(
        node_id=name,
        imports=tuple(imports),
        declarations=tuple(declarations),
        metadata=tuple(metadata),
    )


def minimal(name, *, imports=()):
    return module(
        name,
        GoalNode(f"{name}-goal", "reach_state", "Done"),
        StateNode(f"{name}-state", "Start", "symbolic", {}),
        imports=imports,
    )


class CoreLanguageModelValidation(unittest.TestCase):
    def test_six_core_concepts_lower_without_semantic_loss(self):
        source = module(
            "Workflow",
            GoalNode("goal", "reach_state", "Done"),
            StateNode("state", "Start", "workflow", {"ready": True}),
            TransitionNode(
                "transition",
                "finish",
                "Start",
                "Advance",
                "Done",
                guard="allowed",
                effect={"ready": False},
            ),
            ConstraintNode("constraint", "allowed", "predicate", "ready == true"),
            ContextNode("context", "evidence", "memory", "memory://evidence"),
            metadata=(MetadataNode("metadata", "owner", "language-team"),),
        )
        ir = to_reason_ir(source)

        self.assertEqual(ir["goal"], {"kind": "reach_state", "target": "Done"})
        self.assertEqual(ir["initial_state"]["state_id"], "Start")
        self.assertEqual(ir["transitions"][0]["transition_id"], "finish")
        self.assertEqual(ir["constraints"][0]["constraint_id"], "allowed")
        self.assertEqual(ir["context_refs"][0]["context_id"], "evidence")
        self.assertEqual(ir["metadata"], {"owner": "language-team"})

    def test_metadata_does_not_change_executable_fields(self):
        base = minimal("Base")
        annotated = ModuleNode(
            node_id=base.node_id,
            imports=base.imports,
            declarations=base.declarations,
            metadata=(MetadataNode("metadata", "doc", "annotation"),),
        )
        base_ir = to_reason_ir(base)
        annotated_ir = to_reason_ir(annotated)
        annotated_ir.pop("metadata")
        self.assertEqual(base_ir, annotated_ir)


class ModuleNamespaceValidation(unittest.TestCase):
    def test_local_and_qualified_imported_lookup_are_deterministic(self):
        user = module(
            "User",
            GoalNode("user-goal", "reach_state", "Active"),
            StateNode("user-state", "UserState", "symbolic", {}),
            ConstraintNode("user-active", "Active", "predicate", "enabled"),
        )
        order = module(
            "Order",
            GoalNode("order-goal", "reach_state", "Active"),
            StateNode("order-state", "OrderState", "symbolic", {}),
            ConstraintNode("order-active", "Active", "predicate", "open"),
        )
        app = minimal("App", imports=("User", "Order"))
        resolved = resolve_modules({"User": user, "Order": order, "App": app})

        self.assertEqual(resolved["App"].resolve("Start").kind, SymbolKind.STATE)
        self.assertEqual(
            resolved["App"].resolve("User.Active").qualified_name, "User.Active"
        )
        self.assertEqual(
            resolved["App"].resolve("Order.Active").qualified_name, "Order.Active"
        )
        with self.assertRaises(UnknownSymbolError):
            resolved["App"].resolve("Active")

    def test_unknown_modules_and_cycles_are_rejected(self):
        with self.assertRaises(UnknownModuleError):
            resolve_modules({"App": minimal("App", imports=("Missing",))})
        with self.assertRaises(ImportCycleError):
            resolve_modules(
                {
                    "A": minimal("A", imports=("B",)),
                    "B": minimal("B", imports=("A",)),
                }
            )

    def test_qualified_lookup_uses_the_longest_module_name(self):
        user = minimal("User")
        admin = module(
            "User.Admin",
            GoalNode("admin-goal", "reach_state", "Done"),
            StateNode("admin-state", "AdminState", "symbolic", {}),
        )
        app = minimal("App", imports=("User", "User.Admin"))
        resolved = resolve_modules(
            {"User": user, "User.Admin": admin, "App": app}
        )
        self.assertEqual(
            resolved["App"].resolve("User.Admin.AdminState").qualified_name,
            "User.Admin.AdminState",
        )

    def test_namespace_collisions_across_concept_kinds_are_rejected(self):
        invalid = module(
            "Collision",
            GoalNode("goal", "reach_state", "Done"),
            StateNode("state", "same", "symbolic", {}),
            ConstraintNode("constraint", "same", "predicate", "true"),
        )
        with self.assertRaisesRegex(ModuleResolutionError, "duplicate exported symbol"):
            resolve_modules({"Collision": invalid})


if __name__ == "__main__":
    unittest.main()
