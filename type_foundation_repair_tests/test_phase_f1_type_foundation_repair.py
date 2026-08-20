"""Phase F1 — Type Foundation Repair regression tests (RS-RE-FSM-001 §12.1).

Covers the defects verified against v0.5.4.6 during design (D-3, D-4, D-5)
and fixed in this Phase. D-1 (untyped parameter inference) and D-2 (return
type inference) are intentionally deferred: an initial full-strictness
implementation broke a codebase-wide convention of undeclared placeholder
calls (`notify(x)`, `publish(order)`) used across 16 existing test files as
generic "effectful statement" stand-ins, and 30+ existing fixtures declare
functions with untyped parameters. Fixing D-1/D-2 safely requires enumerating
and migrating that exposure, which is out of scope for this Phase.
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
