"""reason-computation-ir/0.2 — schema constants.

This is the "Reason Computation IR" from the ReasonScript modernization
plan (section 6), kept separate from the pre-existing `reason-ir/0.1`
(state/goal/transition/constraint IR — see `toolchain.artifacts`). This
IR is specifically for lowering executable calculation/function bodies
(control flow + Tensor calls) to a basic-block form, as a step toward a
future Rust computation runtime.

Everything here is plain JSON-serializable `dict`/`list`/scalar data
(matching the plan's "Python frontend generates canonical JSON" transfer
rule in section 6), not a dataclass hierarchy — this is what will
eventually cross the Python/Rust boundary as JSON, so no Python-specific
object identity or types should be relied upon by any downstream reader.

0.2 adds `enum`, `optional` (`some(...)`/`none`), and `match` as tagged
values with real pattern matching (Phase 1 of the enum/optional/match
unification plan): the `enum_value`/`optional_some`/`optional_none`
expression ops, and the `match` terminator kind together with the
`PATTERN_KINDS` vocabulary consumed by its `arms`. `null` (`NullLiteralNode`)
keeps lowering to plain `const:null` as before, distinct from `none`
(`NoneLiteralNode`, now `optional_none`) — the two are no longer collapsed
into the same IR shape.
"""

from __future__ import annotations

SCHEMA = "reason-computation-ir/0.2"

TERMINATOR_KINDS = ("jump", "branch", "return", "result", "trap", "match")

# Expression IR node "op" tags. Deliberately not exhaustive over the full
# ReasonScript language surface: scope is bounded to what
# `frontend.integrated_computation_runtime` (the AST evaluator this IR is
# differentially tested against) itself supports. Constructs outside this
# set (map/set literals, reason_object graph queries) are out of scope for
# this phase and are rejected by the lowering with a clear "not supported"
# error rather than silently mishandled.
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
    "call_reasoning",
    "call_array_append",
    "call_function",
    "call_cast",
    "enum_value",
    "optional_some",
    "optional_none",
)

INSTRUCTION_OPS = (
    "assign", "index_assign", "field_assign", "expr",
    "trace_loop_start", "trace_loop_end",
)

# Pattern "kind" tags used inside a `match` terminator's `arms`. Shared
# vocabulary between `lowering.py` (AST Pattern -> JSON), `interpreter.py`
# (JSON -> Python match), and the Rust decoder/VM (`ir.rs`/`vm.rs`'s
# `Pattern` enum) -- all three must agree on this shape.
#
# `wildcard` covers both `_` (WildcardPatternNode) and `default`
# (DefaultPatternNode): both match unconditionally with no binding.
# `binding` covers both a bare identifier pattern and a struct
# shorthand/rename binding (StructBindingPatternNode): matches
# unconditionally and binds `name`.
# `optional_some` always carries a nested `pattern` (a `binding` or
# `wildcard` for the simple `Some(x)`/`Some(_)` forms, anything else for
# `Some(<nested pattern>)`), unifying OptionalPatternNode and
# OptionalValuePatternNode into one IR shape.
PATTERN_KINDS = (
    "wildcard",
    "binding",
    "literal",
    "range",
    "enum_value",
    "optional_some",
    "optional_none",
    "struct",
    "or",
)
