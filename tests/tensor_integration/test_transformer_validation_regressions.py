from __future__ import annotations

import pytest

from frontend.integrated_computation_runtime import execute_program
from frontend.language_surface import SurfaceSyntaxError, parse


def test_tensor_scalar_can_be_used_in_comparison_and_logical_expression() -> None:
    comparison = parse(
        """module ScalarComparison {
  calculation Answer {
    let value = tensor.create([1.0], "f64")
    result = tensor.scalar(value) > 0.0
  }
}
"""
    )
    assert execute_program(comparison).to_dict()["result"] is True

    logical = parse(
        """module ScalarLogical {
  calculation Answer {
    let value = tensor.create([true], "bool")
    result = tensor.scalar(value) && true
  }
}
"""
    )
    assert execute_program(logical).to_dict()["result"] is True


def test_integer_division_is_statistically_float_like_runtime_true_division() -> None:
    program = parse(
        """module TrueDivision {
  calculation Answer -> float {
    result = 3 / 2
  }
}
"""
    )
    assert execute_program(program).to_dict()["result"] == pytest.approx(1.5)

    with pytest.raises(SurfaceSyntaxError, match="TYPE-V003"):
        parse(
            """module TrueDivisionMismatch {
  calculation Answer -> int {
    result = 3 / 2
  }
}
"""
        )


def test_unknown_function_return_can_be_reassigned_to_concrete_tensor() -> None:
    program = parse(
        """module UnknownReturnCompatibility {
  fn make_tensor() {
    return tensor.create([1.0])
  }
  calculation Answer {
    let value = make_tensor()
    value = tensor.create([2.0])
    result = value
  }
}
"""
    )
    assert execute_program(program).to_dict()["result"] == [2.0]


def test_transformer_constraints_remain_explicit() -> None:
    # `flag` has no type annotation and no call site to infer one from, so
    # this is TYPE-020 (declaration-anchored: RS-RE-FSM-001 design doc
    # F1-R.4), not the old distant-use-site FCF-004. The rejection itself
    # (an unresolvable condition type is still illegal) is unchanged.
    with pytest.raises(SurfaceSyntaxError, match="TYPE-020"):
        parse(
            """module UntypedCondition {
  fn choose(flag) -> int {
    if flag {
      return 1
    }
    return 0
  }
}
"""
        )

    with pytest.raises(SurfaceSyntaxError, match="unsupported function statement"):
        parse(
            """module WrappedExpression {
  fn choose(flag: bool) -> bool {
    return flag
      && true
  }
}
"""
        )
