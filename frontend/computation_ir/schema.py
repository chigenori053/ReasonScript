"""reason-computation-ir/0.1 — schema constants.

This is the "Reason Computation IR" from the ReasonScript modernization
plan (section 6), kept separate from the pre-existing `reason-ir/0.1`
(state/goal/transition/constraint IR — see `toolchain.artifacts`). This
IR is specifically for lowering executable calculation/function bodies
(control flow + Tensor calls) to a basic-block form, as a step toward a
future Rust computation runtime. Phase 2 scope is Python-only: this
module defines the shape of the IR and is consumed by a temporary Python
interpreter (`frontend.computation_ir.interpreter`), not by any Rust
code yet.

Everything here is plain JSON-serializable `dict`/`list`/scalar data
(matching the plan's "Python frontend generates canonical JSON" transfer
rule in section 6), not a dataclass hierarchy — this is what will
eventually cross the Python/Rust boundary as JSON, so no Python-specific
object identity or types should be relied upon by any downstream reader.
"""

from __future__ import annotations

SCHEMA = "reason-computation-ir/0.1"

TERMINATOR_KINDS = ("jump", "branch", "return", "result", "trap")

# Expression IR node "op" tags. Deliberately not exhaustive over the full
# ReasonScript language surface: scope is bounded to what
# `frontend.integrated_computation_runtime` (the AST evaluator this IR is
# differentially tested against) itself supports. Constructs outside this
# set (pattern matching, Optional/Some, map/set literals, reason_object graph
# queries, runtime.search/simulate/predict/plan)
# are out of scope for this phase and are rejected by the lowering with a
# clear "not supported" error rather than silently mishandled.
EXPRESSION_OPS = (
    "const",
    "local",
    "array",
    "struct",
    "unary",
    "binary",
    "comparison",
    "logical",
    "index",
    "member",
    "call_tensor",
    "call_vision",
    "call_ruo",
    "call_optimizer",
    "call_relation",
    "call_array_append",
    "call_function",
    "call_cast",
)

INSTRUCTION_OPS = ("assign", "index_assign", "field_assign", "expr")
