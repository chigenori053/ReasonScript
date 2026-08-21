"""Phase F1 — Type Foundation Repair regression tests (RS-RE-FSM-001 §12.1).

Covers the defects verified against v0.5.4.6 during design (D-3, D-4, D-5),
plus D-1 (untyped parameter inference) and D-2 (return type inference),
implemented per the F1-R redesign (design doc) after a full-corpus
measurement disproved the original F1-1/F1-2 plan: 14 of 15 untyped-
parameter functions in the corpus have no call site in their own module,
including `reason init`'s own starter template (`fn run(goal) { return
goal }`). The redesign never rejects a function on that basis -- it
attempts call-site inference (F1-1r tier 1, never errors) and only reports
`TYPE-020`, anchored at the parameter's own declaration, when an untyped,
uninferred parameter actually reaches a position that demands a concrete
type. D-2's `TYPE-021` (conflicting return types) is enabled outright: the
corpus's one real conflict (platform_phase8_tests/test_runtime_namespace_api.py)
was an incidental match-arm inconsistency unrelated to what that test
verifies, and was fixed alongside this stage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from frontend.integrated_computation_runtime import execute_program
from frontend.language_surface.parser import parse
from toolchain.pipeline import PipelineError, validate_source

PATH = Path("phase_f1.rsn")


def compiles(source: str) -> None:
    validate_source(source, PATH)


def run_value(source: str):
    return execute_program(parse(source)).value


# --- D-5: Int / Int static type now matches the true-division runtime ------


def test_int_division_static_type_is_float() -> None:
    compiles(
        """
        module M {
          calculation C {
            let a = 7
            let b = 2
            let c: float = a / b
            result = c
          }
        }
        """
    )


def test_int_division_runtime_value_is_unchanged() -> None:
    assert run_value(
        """
        module M {
          calculation C {
            let a = 7
            let b = 2
            result = a / b
          }
        }
        """
    ) == pytest.approx(3.5)


def test_int_division_assigned_to_int_annotation_is_rejected() -> None:
    with pytest.raises(PipelineError):
        compiles(
            """
            module M {
              calculation C {
                let a = 7
                let b = 2
                let c: int = a / b
                result = c
              }
            }
            """
        )


# --- D-4: float()/int() explicit numeric conversion builtins ---------------


def test_float_conversion_compiles_and_runs() -> None:
    compiles(
        """
        module M {
          calculation C {
            let count = 3
            let value: float = float(count)
            result = value
          }
        }
        """
    )
    assert run_value(
        """
        module M {
          calculation C {
            let count = 3
            result = float(count)
          }
        }
        """
    ) == 3.0


def test_int_conversion_truncates_toward_zero() -> None:
    assert run_value(
        """
        module M {
          calculation C {
            result = int(3.7)
          }
        }
        """
    ) == 3
    assert run_value(
        """
        module M {
          calculation C {
            result = int(-3.7)
          }
        }
        """
    ) == -3


def test_numeric_conversion_rejects_non_numeric_argument() -> None:
    with pytest.raises(PipelineError, match="FN-013"):
        compiles(
            """
            module M {
              calculation C {
                let s = "hi"
                result = float(s)
              }
            }
            """
        )


def test_numeric_conversion_rejects_wrong_argument_count() -> None:
    with pytest.raises(PipelineError, match="FN-012"):
        compiles(
            """
            module M {
              calculation C {
                result = float(1, 2)
              }
            }
            """
        )


def test_undeclared_placeholder_calls_remain_permitted() -> None:
    # Codebase-wide convention: bare calls to undeclared identifiers used as
    # generic "effectful statement" stand-ins must still compile.
    compiles(
        """
        module M {
          calculation C {
            notify(1)
            result = 1
          }
        }
        """
    )


# --- D-3: tensor.to_array() result is indexable -----------------------------


def test_to_array_result_supports_indexing_via_let_binding() -> None:
    compiles(
        """
        module M {
          calculation C {
            let t = tensor.zeros([2], "f32")
            let values = tensor.to_array(t)
            let first: float = values[0]
            result = first
          }
        }
        """
    )


def test_to_array_result_supports_direct_indexing() -> None:
    compiles(
        """
        module M {
          calculation C {
            let t = tensor.zeros([2], "f32")
            let first: float = tensor.to_array(t)[0]
            result = first
          }
        }
        """
    )


def test_to_array_int_dtype_infers_int_element_type() -> None:
    # Element-type inference is scoped to to_array's direct argument
    # (identifier-binding propagation is a documented, deferred limitation
    # -- see docs/development/reason_entity_foundation_design_v0_1.md F1-3).
    compiles(
        """
        module M {
          calculation C {
            let values = tensor.to_array(tensor.create([1, 2], "i32"))
            let first: int = values[0]
            result = first
          }
        }
        """
    )


def test_to_array_element_type_via_let_binding_is_a_known_limitation() -> None:
    # Documents the deferred limitation: shape/dtype inference does not
    # propagate through an intermediate `let` binding, so a 2D tensor
    # constructed via `let` and then to_array'd cannot be doubly indexed
    # yet. Rank defaults to 1, which fails a second index.
    with pytest.raises(PipelineError):
        compiles(
            """
            module M {
              calculation C {
                let a = tensor.zeros([2, 3], "f32")
                let values = tensor.to_array(a)
                let row = values[0]
                let cell: float = row[1]
                result = cell
              }
            }
            """
        )


# --- D-2: return type inference (F1-2r) -------------------------------------


def test_return_type_inferred_from_single_unification() -> None:
    compiles(
        """
        module M {
          fn f(x: int) {
            return x > 1
          }
          calculation C {
            let y = f(2)
            if y {
              result = 1
            } else {
              result = 0
            }
          }
        }
        """
    )


def test_return_type_null_and_unknown_are_excluded_from_unification() -> None:
    # The real corpus fixture this rule exists for: a function returning
    # either a found value or `null` from different paths.
    compiles(
        """
        module M {
          fn find(values: [int], target: int) {
            for value in values {
              if value == target {
                return value
              }
            }
            return null
          }
          calculation C {
            let r = find([1, 2, 3], 2)
            result = 1
          }
        }
        """
    )


def test_conflicting_return_types_raise_type_021() -> None:
    with pytest.raises(PipelineError, match="TYPE-021"):
        compiles(
            """
            module M {
              fn f(x: int) {
                if x > 0 {
                  return 1
                }
                return "s"
              }
              calculation C {
                let y = f(1)
                result = 1
              }
            }
            """
        )


def test_no_return_statements_is_unaffected_by_inference() -> None:
    # FN-010 ("not all paths return") already rejects this; F1-2r must not
    # change that.
    with pytest.raises(PipelineError, match="FN-010"):
        compiles(
            """
            module M {
              fn f(x: int) {
                let y = x + 1
              }
              calculation C {
                result = 1
              }
            }
            """
        )


# --- D-1: parameter type inference (F1-1r) ----------------------------------


def test_reason_init_template_still_compiles() -> None:
    # toolchain/init_cmd.py's exact starter template. The original F1-1
    # design (unconditional TYPE-020 for any 0-call-site parameter) would
    # have broken every project `reason init` creates.
    compiles(
        """
        package hello_world
        module main {
            fn run(goal) {
                return goal
            }
        }
        """
    )


def test_untyped_parameter_never_used_in_a_typed_position_compiles() -> None:
    compiles(
        """
        module M {
          fn identity(value) {
            return value
          }
          calculation C {
            let y = identity(1)
            result = y
          }
        }
        """
    )


def test_untyped_parameter_with_no_call_site_in_condition_raises_type_020() -> None:
    with pytest.raises(PipelineError, match="TYPE-020"):
        compiles(
            """
            module M {
              fn f(flag) {
                if flag {
                  return 1
                }
                return 0
              }
            }
            """
        )


def test_type_020_message_names_the_function_and_parameter() -> None:
    with pytest.raises(PipelineError, match=r"TYPE-020.*`flag`.*`f`"):
        compiles(
            """
            module M {
              fn f(flag) {
                if flag {
                  return 1
                }
                return 0
              }
            }
            """
        )


def test_call_site_literal_argument_is_inferred_and_type_checked() -> None:
    # `f(2)` infers `flag: Int`; `if flag` on an Int is then a genuine,
    # correctly-diagnosed type mismatch (CV-1), not an indirect Unknown
    # artifact (TYPE-020 does not fire here -- the type was inferred).
    with pytest.raises(PipelineError, match="CV-1"):
        compiles(
            """
            module M {
              fn f(flag) {
                if flag {
                  return 1
                }
                return 0
              }
              calculation C {
                let y = f(2)
                result = y
              }
            }
            """
        )


def test_call_site_inference_does_not_resolve_local_bindings() -> None:
    # Conservative by design: the caller's own local `let`/`const` are not
    # resolved (would need the caller's own body already validated, which
    # is circular for mutual calls). `local` stays Unknown at the call
    # site, so no type is inferred for `x` and the function stays legal.
    compiles(
        """
        module M {
          fn f(x) {
            return x
          }
          calculation C {
            let local = 1
            let y = f(local)
            result = y
          }
        }
        """
    )
