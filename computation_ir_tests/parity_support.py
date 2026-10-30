"""Shared source-to-IR parity checks for unittest suites."""
from frontend.computation_ir import interpret_program, lower_program, validate_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import IntegratedRuntimeError, LoopLimitError
from frontend.language_surface import parse
from frontend.tensor import TensorError

BINARY = find_binary()


def python_outcome(ir):
    try:
        result = interpret_program(ir)
    except (IntegratedRuntimeError, LoopLimitError) as error:
        return None, getattr(error, "code", None)
    except TensorError as error:
        return None, error.diagnostic.code
    return dict(result.calculation_results), None


def rust_outcome(ir):
    outcome = run_ir(ir, binary=BINARY)
    return (outcome.calculation_results, None) if outcome.ok else (None, outcome.error_code)


class SourceParityMixin:
    def prepare_ir(self, source):
        return lower_program(parse(source))

    def assert_parity(self, source):
        ir = self.prepare_ir(source)
        self.assertEqual(validate_program(ir), [])
        python_results, python_error = python_outcome(ir)
        if BINARY is not None:
            rust_results, rust_error = rust_outcome(ir)
            self.assertEqual(python_error, rust_error, f"error code mismatch for:\n{source}")
            if python_error is None:
                self.assertEqual(python_results, rust_results, f"result mismatch for:\n{source}")
        return python_results, python_error
