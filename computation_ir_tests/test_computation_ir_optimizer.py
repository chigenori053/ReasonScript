"""Phase 7 ("IR最適化"): `frontend.computation_ir.optimizer`.

Covers constant folding, dead-branch/unreachable-block elimination, dead
local elimination, and local CSE, plus differential parity: every program
here is run through `interpret_program` both unoptimized and optimized
(and, when the Rust binary is built, through the Rust VM too) and the
`calculation_results` / error code must match exactly. Optimization must
never change what a program computes -- only how many instructions it
takes to compute it.
"""

from __future__ import annotations

import unittest

from frontend.computation_ir import interpret_program, lower_program, validate_program
from frontend.computation_ir.optimizer import classify_pure_functions, optimize_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import IntegratedRuntimeError, LoopLimitError
from frontend.language_surface import parse

_BINARY = find_binary()


def _lower(source: str):
    return lower_program(parse(source))


def _python_outcome(ir):
    try:
        result = interpret_program(ir)
    except (IntegratedRuntimeError, LoopLimitError) as error:
        return None, getattr(error, "code", None)
    return dict(result.calculation_results), None


def _rust_outcome(ir):
    outcome = run_ir(ir, binary=_BINARY)
    if outcome.ok:
        return outcome.calculation_results, None
    return None, outcome.error_code


class OptimizerParityMixin:
    def assert_parity(self, source: str):
        """Lowers `source` once, optimizes it, and asserts every backend
        (Python unoptimized, Python optimized, and Rust when available)
        agrees on results / error code."""
        ir = _lower(source)
        self.assertEqual(validate_program(ir), [])
        optimized = optimize_program(ir)
        self.assertEqual(validate_program(optimized), [])

        unopt_results, unopt_error = _python_outcome(ir)
        opt_results, opt_error = _python_outcome(optimized)
        self.assertEqual(unopt_error, opt_error, f"error code mismatch (python) for:\n{source}")
        self.assertEqual(unopt_results, opt_results, f"result mismatch (python) for:\n{source}")

        if _BINARY is not None:
            rust_unopt_results, rust_unopt_error = _rust_outcome(ir)
            rust_opt_results, rust_opt_error = _rust_outcome(optimized)
            self.assertEqual(unopt_error, rust_unopt_error, f"error code mismatch (rust unopt) for:\n{source}")
            self.assertEqual(unopt_results, rust_unopt_results, f"result mismatch (rust unopt) for:\n{source}")
            self.assertEqual(unopt_error, rust_opt_error, f"error code mismatch (rust opt) for:\n{source}")
            self.assertEqual(unopt_results, rust_opt_results, f"result mismatch (rust opt) for:\n{source}")

        return optimized, unopt_results


class ConstantFoldingTests(OptimizerParityMixin, unittest.TestCase):
    def test_arithmetic_is_folded_to_a_single_const(self):
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = 2 + 3 * 4
                }
            }
            """
        )
        self.assertEqual(results, {"Answer": 14})
        instructions = optimized["functions"][0]["blocks"][0]["instructions"]
        terminator = optimized["functions"][0]["blocks"][0]["terminator"]
        self.assertEqual(instructions, [])
        self.assertEqual(terminator["value"], {"op": "const", "kind": "int", "value": 14})

    def test_float_division_folds_to_float_kind(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = 7.0 / 2.0
                }
            }
            """
        )

    def test_comparison_and_logical_short_circuit_fold(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    let a = 3 > 1
                    let b = a && (5 < 2)
                    let c = false || true
                    result = b || c
                }
            }
            """
        )

    def test_cast_calls_fold_on_const_arguments(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = float(3) + float(2.9)
                }
            }
            """
        )

    def test_unary_negate_and_not_fold(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    let a = -(5)
                    let b = !(false)
                    result = a
                }
            }
            """
        )

    def test_divide_by_zero_is_left_unfolded_and_still_raises(self):
        optimized, _ = None, None
        ir = _lower(
            """
            module M {
                calculation Answer {
                    result = 1 / 0
                }
            }
            """
        )
        optimized = optimize_program(ir)
        terminator = optimized["functions"][0]["blocks"][0]["terminator"]
        # Left as a `binary` node -- the optimizer must not try to
        # constant-fold a division by zero into a value.
        self.assertEqual(terminator["value"]["op"], "binary")
        with self.assertRaises(IntegratedRuntimeError) as raised:
            interpret_program(optimized)
        self.assertEqual(raised.exception.code, "RT-ARITH-001")
        if _BINARY is not None:
            outcome = run_ir(optimized, binary=_BINARY)
            self.assertFalse(outcome.ok)
            self.assertEqual(outcome.error_code, "RT-ARITH-001")


class PureFunctionFastPathTests(OptimizerParityMixin, unittest.TestCase):
    def test_small_pure_function_is_classified_and_inlined(self):
        source = """
            module M {
                fn Score(value, scale) {
                    let shifted = value + 1
                    return shifted * scale
                }
                calculation Answer {
                    let input = 4
                    result = Score(input, 3)
                }
            }
        """
        ir = _lower(source)
        classification = classify_pure_functions(ir)["M::Score"]
        self.assertTrue(classification.eligible_for_fast_path)
        optimized, results = self.assert_parity(source)
        self.assertEqual(results, {"Answer": 15})
        calculation = next(function for function in optimized["functions"] if function["id"] == "Answer")
        self.assertNotIn("call_function", repr(calculation))

    def test_unknown_effect_and_recursive_functions_are_not_eligible(self):
        impure = _lower(
            """
            module M {
                fn LoadValue(path) {
                    return tensor.load(path)
                }
                calculation Answer {
                    result = 1
                }
            }
            """
        )
        self.assertFalse(classify_pure_functions(impure)["M::LoadValue"].eligible_for_fast_path)

    def test_more_than_32_instructions_is_not_inlined(self):
        statements = "\n".join(f"let v{index} = value + {index}" for index in range(33))
        source = f"""
            module M {{
                fn Large(value) {{
                    {statements}
                    return v32
                }}
                calculation Answer {{
                    result = Large(1)
                }}
            }}
        """
        ir = _lower(source)
        self.assertFalse(classify_pure_functions(ir)["M::Large"].eligible_for_fast_path)
        optimized = optimize_program(ir)
        calculation = next(function for function in optimized["functions"] if function["id"] == "Answer")
        self.assertIn("call_function", repr(calculation))


class LoopInvariantCodeMotionTests(OptimizerParityMixin, unittest.TestCase):
    SOURCE = """
        module M {
            calculation Answer {
                let base = 4
                let i = 0
                let total = 0
                while i < 3 {
                    let factor = base * 2
                    total = total + factor
                    i = i + 1
                }
                result = total
            }
        }
    """

    def test_total_invariant_computation_is_hoisted(self):
        optimized, results = self.assert_parity(self.SOURCE)
        self.assertEqual(results, {"Answer": 24})
        entry = next(block for block in optimized["functions"][0]["blocks"] if ".entry_" in block["id"])
        self.assertTrue(any(str(item.get("target", "")).startswith("__opt_licm_") for item in entry["instructions"]))

    def test_optimized_loop_trace_is_identical(self):
        ir = _lower(self.SOURCE)
        before = interpret_program(ir).to_dict()["loop_trace"]
        after = interpret_program(optimize_program(ir)).to_dict()["loop_trace"]
        self.assertEqual(before, after)

    def test_potentially_trapping_division_is_not_hoisted(self):
        source = """
            module M {
                calculation Answer {
                    let divisor = 0
                    let i = 0
                    while i < 0 {
                        let unsafe = 10 / divisor
                        i = i + 1
                    }
                    result = 1
                }
            }
        """
        optimized, results = self.assert_parity(source)
        self.assertEqual(results, {"Answer": 1})
        self.assertNotIn("__opt_licm_", repr(optimized))

    def test_modulo_by_zero_is_left_unfolded_and_still_raises(self):
        ir = _lower(
            """
            module M {
                calculation Answer {
                    result = 5 % 0
                }
            }
            """
        )
        optimized = optimize_program(ir)
        with self.assertRaises(IntegratedRuntimeError) as raised:
            interpret_program(optimized)
        self.assertEqual(raised.exception.code, "RT-ARITH-001")


class BranchAndDeadCodeTests(OptimizerParityMixin, unittest.TestCase):
    def test_true_branch_collapses_to_jump_and_removes_else_block(self):
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let x = 0
                    if true {
                        x = 1
                    } else {
                        x = 2
                    }
                    result = x
                }
            }
            """
        )
        self.assertEqual(results, {"Answer": 1})
        blocks = optimized["functions"][0]["blocks"]
        # Only reachable blocks survive: entry + then-branch (+ join, if
        # the lowering produces one) -- never the else-branch's block.
        for block in blocks:
            for instruction in block["instructions"]:
                if instruction["op"] == "assign":
                    self.assertNotEqual(
                        instruction.get("expr"), {"op": "const", "kind": "int", "value": 2}
                    )

    def test_false_branch_collapses_to_jump(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    let x = 0
                    if false {
                        x = 1
                    } else {
                        x = 2
                    }
                    result = x
                }
            }
            """
        )

    def test_unused_let_binding_is_eliminated(self):
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let a = 2
                    let b = 3
                    let unused = 999
                    result = a + b
                }
            }
            """
        )
        self.assertEqual(results, {"Answer": 5})
        for block in optimized["functions"][0]["blocks"]:
            for instruction in block["instructions"]:
                self.assertNotEqual(instruction.get("target"), "unused")

    def test_tensor_save_is_never_eliminated_even_when_unused(self):
        ir = _lower(
            """
            module M {
                calculation Answer {
                    let a = tensor.create([1.0, 2.0], "f64")
                    let receipt = tensor.save(a, "unused_output.rstensor", true)
                    result = tensor.to_array(a)
                }
            }
            """
        )
        optimized = optimize_program(ir)
        save_calls = [
            instruction
            for block in optimized["functions"][0]["blocks"]
            for instruction in block["instructions"]
            if instruction.get("op") == "assign"
            and instruction["expr"].get("op") == "call_tensor"
            and instruction["expr"].get("function_id") == "tensor.save"
        ]
        self.assertEqual(len(save_calls), 1)

    def test_tensor_load_is_never_eliminated_even_when_unused(self):
        ir = _lower(
            """
            module M {
                calculation Answer {
                    let unused = tensor.load("does_not_matter.rstensor")
                    result = 1
                }
            }
            """
        )
        optimized = optimize_program(ir)
        load_calls = [
            instruction
            for block in optimized["functions"][0]["blocks"]
            for instruction in block["instructions"]
            if instruction.get("op") == "assign"
            and instruction["expr"].get("op") == "call_tensor"
            and instruction["expr"].get("function_id") == "tensor.load"
        ]
        self.assertEqual(len(load_calls), 1)


class LocalCseTests(OptimizerParityMixin, unittest.TestCase):
    def test_repeated_pure_expression_is_deduplicated(self):
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let a = 2
                    let b = 3
                    let c = a + b
                    let d = a + b
                    result = c + d
                }
            }
            """
        )
        self.assertEqual(results, {"Answer": 10})
        instructions = optimized["functions"][0]["blocks"][0]["instructions"]
        d_instruction = next(instruction for instruction in instructions if instruction.get("target") == "d")
        self.assertEqual(d_instruction["expr"], {"op": "local", "name": "c"})

    def test_self_referential_assign_is_not_cached_and_does_not_poison_later_reads(self):
        # `i = i + 1` must never populate the CSE cache under the key for
        # `i + 1`: a *later*, syntactically identical `i + 1` refers to
        # the *new* value of `i` and must not collapse to plain `i`.
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let i = 0
                    i = i + 1
                    let j = i + 1
                    result = j
                }
            }
            """
        )
        self.assertEqual(results, {"Answer": 2})
        instructions = optimized["functions"][0]["blocks"][0]["instructions"]
        j_instruction = next(instruction for instruction in instructions if instruction.get("target") == "j")
        # Must still be a real binary add, not a wrongly-cached bare local.
        self.assertEqual(j_instruction["expr"]["op"], "binary")

    def test_reassignment_invalidates_cached_expressions_reading_old_value(self):
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let x = 1
                    let a = x + 1
                    x = 5
                    let b = x + 1
                    result = a + b
                }
            }
            """
        )
        self.assertEqual(results, {"Answer": 8})
        instructions = optimized["functions"][0]["blocks"][0]["instructions"]
        b_instruction = next(instruction for instruction in instructions if instruction.get("target") == "b")
        self.assertNotEqual(b_instruction["expr"], {"op": "local", "name": "a"})

    def test_tensor_calls_are_never_deduplicated(self):
        # Both `a` and `b` are read (by the final add), so dead-local
        # elimination cannot remove either -- this isolates CSE as the
        # only pass that could merge the two structurally-identical
        # `tensor.create` calls, and confirms it deliberately does not.
        ir = _lower(
            """
            module M {
                calculation Answer {
                    let a = tensor.create([1.0], "f64")
                    let b = tensor.create([1.0], "f64")
                    result = tensor.to_array(tensor.add(a, b))
                }
            }
            """
        )
        optimized = optimize_program(ir)
        create_calls = [
            instruction
            for block in optimized["functions"][0]["blocks"]
            for instruction in block["instructions"]
            if instruction.get("op") == "assign"
            and instruction["expr"].get("op") == "call_tensor"
            and instruction["expr"].get("function_id") == "tensor.create"
        ]
        self.assertEqual(len(create_calls), 2)

    def test_optimizer_calls_are_never_deduplicated(self):
        # Same rationale as test_tensor_calls_are_never_deduplicated:
        # `optimizer.sgd` is pure (so unused results ARE eliminated, see
        # OptimizerFunctionsInteractionTests below), but a structurally
        # identical, both-read pair must not be CSE-merged -- an
        # optimizer step is exactly the kind of call whose two
        # "identical" invocations are conceptually a repeated action, not
        # interchangeable values, matching how call_tensor is treated.
        ir = _lower(
            """
            module M {
                calculation Answer {
                    let w = tensor.create([1.0], "f64")
                    let g = tensor.create([0.1], "f64")
                    let a = optimizer.sgd(w, g, 0.5)
                    let b = optimizer.sgd(w, g, 0.5)
                    result = tensor.to_array(tensor.add(a, b))
                }
            }
            """
        )
        optimized = optimize_program(ir)
        sgd_calls = [
            instruction
            for block in optimized["functions"][0]["blocks"]
            for instruction in block["instructions"]
            if instruction.get("op") == "assign"
            and instruction["expr"].get("op") == "call_optimizer"
            and instruction["expr"].get("function_id") == "optimizer.sgd"
        ]
        self.assertEqual(len(sgd_calls), 2)


class OptimizerFunctionsInteractionTests(OptimizerParityMixin, unittest.TestCase):
    """The Phase 7 IR optimizer's interaction with the `optimizer.*`
    namespace itself (added after this file was first written): an
    unused optimizer step is dead-code-eliminated, and a used one
    survives optimization with an identical result."""

    def test_unused_optimizer_step_is_eliminated(self):
        ir = _lower(
            """
            module M {
                calculation Answer {
                    let w = tensor.create([1.0], "f64")
                    let g = tensor.create([0.1], "f64")
                    let unused = optimizer.sgd(w, g, 0.9)
                    result = tensor.to_array(w)
                }
            }
            """
        )
        optimized = optimize_program(ir)
        for block in optimized["functions"][0]["blocks"]:
            for instruction in block["instructions"]:
                self.assertNotEqual(instruction.get("target"), "unused")

    def test_optimizer_step_program_survives_optimization(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    let w = tensor.create([1.0, 2.0], "f64")
                    let g = tensor.create([0.1, 0.2], "f64")
                    let unused = optimizer.sgd(w, g, 0.1)
                    let updated = optimizer.sgd(w, g, 0.5)
                    result = tensor.to_array(updated)
                }
            }
            """
        )


class RelationFunctionsInteractionTests(OptimizerParityMixin, unittest.TestCase):
    """The Phase 7 IR optimizer's interaction with the `relation.*`
    namespace (Phase 8): an unused relation call is dead-code-eliminated,
    a used one survives optimization with an identical result, and two
    structurally-identical calls are never CSE-merged (a comparison can
    raise on an incomparable field type)."""

    def test_unused_relation_call_is_eliminated(self):
        ir = _lower(
            """
            module M {
                struct Row {
                    age: int
                }
                calculation Answer {
                    let rows = [Row { age: 1 }, Row { age: 2 }]
                    let unused = relation.filter_gt(rows, "age", 1)
                    result = relation.count(rows)
                }
            }
            """
        )
        optimized = optimize_program(ir)
        for block in optimized["functions"][0]["blocks"]:
            for instruction in block["instructions"]:
                self.assertNotEqual(instruction.get("target"), "unused")

    def test_relation_pipeline_survives_optimization(self):
        self.assert_parity(
            """
            module M {
                struct Row {
                    age: int
                }
                calculation Answer {
                    let rows = [Row { age: 1 }, Row { age: 2 }, Row { age: 3 }]
                    let unused = relation.filter_gt(rows, "age", 100)
                    let filtered = relation.filter_gt(rows, "age", 1)
                    result = relation.count(filtered)
                }
            }
            """
        )

    def test_relation_calls_are_never_deduplicated(self):
        ir = _lower(
            """
            module M {
                struct Row {
                    age: int
                }
                calculation Answer {
                    let rows = [Row { age: 1 }, Row { age: 2 }]
                    let a = relation.filter_gt(rows, "age", 1)
                    let b = relation.filter_gt(rows, "age", 1)
                    result = relation.count(a) + relation.count(b)
                }
            }
            """
        )
        optimized = optimize_program(ir)
        filter_calls = [
            instruction
            for block in optimized["functions"][0]["blocks"]
            for instruction in block["instructions"]
            if instruction.get("op") == "assign"
            and instruction["expr"].get("op") == "call_relation"
            and instruction["expr"].get("function_id") == "relation.filter_gt"
        ]
        self.assertEqual(len(filter_calls), 2)


class StringFunctionsInteractionTests(OptimizerParityMixin, unittest.TestCase):
    """Phase 2: the `string.*` namespace and `array.concat`'s interaction
    with the optimizer -- an unused call is dead-code-eliminated (and,
    for `string.*`, a local read only inside its `arguments` must still
    count as "used" -- `_collect_reads` needed an explicit `call_string`
    branch or a local read only there would look dead), a used pipeline
    survives optimization with an identical result, and repeated calls
    are never CSE-merged (matching every other namespaced call)."""

    def test_unused_string_call_is_eliminated(self):
        ir = _lower(
            """
            module M {
                calculation Answer {
                    let unused = string.concat("a", "b")
                    result = 1
                }
            }
            """
        )
        optimized = optimize_program(ir)
        for block in optimized["functions"][0]["blocks"]:
            for instruction in block["instructions"]:
                self.assertNotEqual(instruction.get("target"), "unused")

    def test_local_read_only_inside_string_call_arguments_is_not_eliminated(self):
        ir = _lower(
            """
            module M {
                calculation Answer {
                    let piece = "hello"
                    result = string.length(piece)
                }
            }
            """
        )
        optimized = optimize_program(ir)
        assigns = [
            instruction
            for block in optimized["functions"][0]["blocks"]
            for instruction in block["instructions"]
            if instruction.get("op") == "assign" and instruction.get("target") == "piece"
        ]
        self.assertEqual(len(assigns), 1)

    def test_string_and_array_concat_pipeline_survives_optimization(self):
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let unused = string.from_int(999)
                    let combined = string.concat("foo", "bar")
                    let letters = array.concat(["f", "o", "o"], ["b", "a", "r"])
                    result = string.length(combined) * 100 + letters.length
                }
            }
            """
        )
        self.assertEqual(results["Answer"], 606)
        del optimized

    def test_string_calls_are_never_deduplicated(self):
        ir = _lower(
            """
            module M {
                calculation Answer {
                    let a = string.concat("x", "y")
                    let b = string.concat("x", "y")
                    result = string.length(a) + string.length(b)
                }
            }
            """
        )
        optimized = optimize_program(ir)
        concat_calls = [
            instruction
            for block in optimized["functions"][0]["blocks"]
            for instruction in block["instructions"]
            if instruction.get("op") == "assign"
            and instruction["expr"].get("op") == "call_string"
            and instruction["expr"].get("function_id") == "string.concat"
        ]
        self.assertEqual(len(concat_calls), 2)


class MatchOptimizationTests(OptimizerParityMixin, unittest.TestCase):
    """Phase 1: the `match` terminator and `enum_value`/`optional_some`/
    `optional_none` expressions must survive every optimizer pass intact.

    `match` arm blocks are only reachable via a terminator's `arms[].target`
    list, not `jump`/`branch`'s `target`/`then`/`else` -- unreachable-block
    removal, predecessor computation, and loop-region detection all needed
    dedicated `match` handling (`_terminator_targets`) or they would treat
    every arm block as unreachable and delete it out from under the
    `match` terminator that still references it.
    """

    def test_enum_match_survives_unreachable_block_removal(self):
        # Each arm assigns and falls through to the match's merge block
        # (rather than every arm unconditionally `return`ing) so the merge
        # block itself stays reachable -- an all-`return` match/if's merge
        # block is *already*, pre-existing-ly, reported unreachable by
        # `validate_program` (the same is true of `_lower_if`, unrelated
        # to Phase 1); that's a separate, narrower lowering quirk this
        # test isn't about, so it's avoided here rather than masked.
        optimized, results = self.assert_parity(
            """
            module M {
                enum Color {
                    Red
                    Blue
                    Green
                }

                calculation Answer {
                    let color = Color.Blue
                    let score = 0
                    match color {
                        Color.Red => {
                            score = 1
                        }
                        Color.Blue => {
                            score = 2
                        }
                        default => {
                            score = 0
                        }
                    }
                    result = score
                }
            }
            """
        )
        self.assertEqual(results["Answer"], 2)
        answer_fn = next(f for f in optimized["functions"] if f["id"] == "Answer")
        block_ids = {block["id"] for block in answer_fn["blocks"]}
        match_terminators = [
            block["terminator"]
            for block in answer_fn["blocks"]
            if block["terminator"]["kind"] == "match"
        ]
        self.assertEqual(len(match_terminators), 1)
        for arm in match_terminators[0]["arms"]:
            self.assertIn(arm["target"], block_ids)

    def test_optional_some_binding_is_not_treated_as_dead_by_local_elimination(self):
        # `y` is read only inside the match `subject` -- `_eliminate_dead_locals`
        # must see that read (via the match terminator's `subject`, not
        # `condition`/`value`) or it would drop `let y = some(5)` and the
        # match dispatch would fail against an undefined local.
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let y = some(5)
                    let outcome = -1
                    match y {
                        some(x) => {
                            outcome = x
                        }
                        none => {
                            outcome = -1
                        }
                    }
                    result = outcome
                }
            }
            """
        )
        self.assertEqual(results["Answer"], 5)
        answer_fn = next(f for f in optimized["functions"] if f["id"] == "Answer")
        assigns = [
            instruction
            for block in answer_fn["blocks"]
            for instruction in block["instructions"]
            if instruction.get("op") == "assign" and instruction.get("target") == "y"
        ]
        self.assertEqual(len(assigns), 1)

    def test_match_inside_while_loop_does_not_corrupt_licm(self):
        # A mutation that happens only inside a match arm (`total` here)
        # must still count as "mutated within the loop" for LICM's
        # hoisting-eligibility check -- otherwise `_loop_region`'s
        # traversal silently stopping at the `match` terminator could let
        # LICM hoist something that reads a value the loop actually
        # changes underneath it.
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let total = 0
                    let i = 0
                    while i < 5 {
                        match i {
                            0 | 2 | 4 => {
                                let step = total + i
                                total = step
                            }
                            default => {
                                let step = total
                                total = step
                            }
                        }
                        i = i + 1
                    }
                    result = total
                }
            }
            """
        )
        self.assertEqual(results["Answer"], 6)
        del optimized


class TensorDifferentialTests(OptimizerParityMixin, unittest.TestCase):
    def test_matmul_program_survives_optimization(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    let a = tensor.create([[1.0, 2.0], [3.0, 4.0]], "f64")
                    let b = tensor.create([[5.0, 6.0], [7.0, 8.0]], "f64")
                    let unused = tensor.create([0.0], "f64")
                    result = tensor.to_array(tensor.matmul(a, b))
                }
            }
            """
        )

    def test_gradient_descent_step_survives_optimization(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    let w = tensor.parameter(tensor.create([1.0, 2.0], "f64"))
                    let target = tensor.create([2.0, 2.0], "f64")
                    let diff = tensor.subtract(w, target)
                    let loss = tensor.sum(tensor.multiply(diff, diff))
                    let grads = tensor.grad(loss, [w])
                    let updated = tensor.subtract(w, tensor.multiply(grads[0], 0.1))
                    result = tensor.to_array(updated)
                }
            }
            """
        )


if __name__ == "__main__":
    unittest.main()
