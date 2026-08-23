"""Differential harness: AST evaluator vs. IR lowering + interpreter.

Implements the Phase 2 gate from the modernization plan: "Python AST/IR
evaluatorが同一結果" — for any program within this IR's supported subset,
`frontend.integrated_computation_runtime.execute_program` and
`lower_program` + `interpret_program` must agree on the resulting
`calculations` dict, or agree on which `IntegratedRuntimeError`/
`LoopLimitError` code they raise.

Known scope limit: a `calculation`'s `result` should be a plain,
structurally-comparable value (numbers, strings, bools, arrays, structs,
or an array/scalar obtained via `tensor.to_array`/`tensor.scalar`) rather
than a raw `Tensor` handle. The AST and IR runs each construct their own
`TensorRuntime`, so two `TensorValueRef`s referring to equal Tensors from
the two runs are still different Python objects and would compare
unequal by identity -- that isn't a real divergence, just a limitation of
comparing opaque handles across two separate runtime instances.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from frontend.integrated_computation_runtime import (
    IntegratedRuntimeError,
    LoopLimitError,
    execute_program,
)
from frontend.language_surface import parse

from .interpreter import interpret_program
from .lowering import lower_program


@dataclass
class DifferentialOutcome:
    calculations: dict[str, Any] | None
    error_code: str | None
    error_type: str | None


def _run_ast(source: str) -> DifferentialOutcome:
    program = parse(source)
    try:
        result = execute_program(program)
    except (IntegratedRuntimeError, LoopLimitError) as error:
        code = getattr(error, "code", None)
        return DifferentialOutcome(None, code, type(error).__name__)
    return DifferentialOutcome(dict(result.calculation_results), None, None)


def _run_ir(source: str) -> DifferentialOutcome:
    program = parse(source)
    ir = lower_program(program)
    try:
        result = interpret_program(ir)
    except (IntegratedRuntimeError, LoopLimitError) as error:
        code = getattr(error, "code", None)
        return DifferentialOutcome(None, code, type(error).__name__)
    return DifferentialOutcome(dict(result.calculation_results), None, None)


def assert_same_outcome(source: str) -> DifferentialOutcome:
    """Run `source` through both evaluators and assert they agree.

    Returns the AST evaluator's outcome (for further assertions by the
    caller) if both sides match; raises `AssertionError` describing the
    mismatch otherwise.
    """
    ast_outcome = _run_ast(source)
    ir_outcome = _run_ir(source)
    if ast_outcome != ir_outcome:
        raise AssertionError(
            "AST and IR evaluators disagree:\n"
            f"  AST: {ast_outcome}\n"
            f"  IR:  {ir_outcome}\n"
            f"  source:\n{source}"
        )
    return ast_outcome
