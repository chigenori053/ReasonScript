"""Phase 7 "IR最適化" — optimization passes over `reason-computation-ir/0.1`.

Runs entirely on the Python side, on the same JSON `lower_program`
produces, so a single implementation benefits both consumers of the IR:
`frontend.computation_ir.interpreter` (Python) and the Rust
`reason-computation-runtime` (`ReasonComputationRuntime/`) -- optimizing
the IR once optimizes both backends, rather than duplicating passes in
two languages.

Implements the subset of the plan's Phase 7 pipeline (section 7) that
applies to this IR's actual shape:

- constant folding (`_fold_expr`): evaluates expression subtrees whose
  operands are all `const` nodes, using Python's own arithmetic -- which
  is what `frontend.computation_ir.interpreter` would compute anyway, so
  folding never changes what a *valid* program evaluates to. A fold that
  would raise (division/modulo by zero) is deliberately left unfolded so
  the runtime still raises the correct RT-ARITH-001 at the right point,
  rather than the optimizer trying to encode "this constant-folds to an
  error."
- dead branch elimination (`_simplify_branches`): a `branch` terminator
  whose folded condition is a constant Bool becomes an unconditional
  `jump`, per the plan's "3. dead branch/tensor elimination".
- unreachable block removal (`_remove_unreachable_blocks`): blocks no
  longer reachable after branch simplification are dropped.
- dead local elimination (`_eliminate_dead_locals`): an `assign` whose
  target is never read anywhere else in the function, and whose
  expression has no side effect, is removed. `tensor.save` (file I/O)
  and RNG calls are excluded from this pass entirely, even when
  seemingly unused, since dropping them would change program behavior
  observable outside the `calculations` result (a written file; and
  while RNG *is* a pure function of its explicit seed/stream/counter,
  it's still excluded defensively rather than special-cased, since nothing
  in this repository needs "unused random Tensor" elimination badly enough
  to justify the extra branch in an already-conservative pass).
- local common-subexpression elimination (`_local_cse`): within a single
  straight-line block (no branches to reason about), a repeated
  structurally-identical *pure* expression is replaced with a reference
  to the local that already holds its value. `call_tensor`/`call_vision`/
  `call_function`/`call_array_append` are treated as impure (never
  deduplicated) -- Tensor calls can raise (shape/dtype errors), and a
  user function can itself contain a `tensor.save`, so CSE-ing them
  would risk skipping a side effect or an error a second occurrence
  should still raise.

NOT implemented (documented, not silent): cross-block CSE, loop-invariant
code motion/hoisting, a Relation Matrix-style cache (no relation engine
exists to cache against), gradient pruning as a *compile-time* IR pass
(the interpreter and Rust VM already only walk tape nodes reachable from
the requested loss at `grad()`-call time -- see
`ReasonComputationRuntime/crates/tensor-core/src/autograd.rs` -- which is
this codebase's form of "don't generate a VJP that can't reach the
loss"), liveness-driven Tensor buffer reuse, and kernel fusion
(`fused softmax`/batched matmul don't apply: `softmax` isn't implemented
at all, per Phase 4's scope, and `matmul` is rank-2 / unbatched only).
"""

from __future__ import annotations

import copy
from typing import Any

_BINARY_FOLD = {
    "Add": lambda a, b: a + b,
    "Subtract": lambda a, b: a - b,
    "Multiply": lambda a, b: a * b,
    "Divide": lambda a, b: a / b,
    "Modulo": lambda a, b: a % b,
}

_COMPARISON_FOLD = {
    "Equal": lambda a, b: a == b,
    "NotEqual": lambda a, b: a != b,
    "GreaterThan": lambda a, b: a > b,
    "GreaterThanOrEqual": lambda a, b: a >= b,
    "LessThan": lambda a, b: a < b,
    "LessThanOrEqual": lambda a, b: a <= b,
}


def optimize_program(document: dict[str, Any]) -> dict[str, Any]:
    """Returns a new, optimized `reason-computation-ir/0.1` document.

    `document` is not mutated. Safe to run repeatedly (idempotent modulo
    block/local renumbering never happening -- this pass never
    introduces new ids).
    """
    optimized = copy.deepcopy(document)
    optimized["functions"] = [_optimize_function(function) for function in optimized["functions"]]
    return optimized


def _optimize_function(function: dict[str, Any]) -> dict[str, Any]:
    blocks_by_id = {block["id"]: _fold_block(block) for block in function["blocks"]}
    blocks_by_id = _simplify_branches(blocks_by_id)
    order = [block["id"] for block in function["blocks"]]
    reachable = _reachable_block_ids(blocks_by_id, function["entry_block"])
    order = [block_id for block_id in order if block_id in reachable]
    blocks_by_id = _eliminate_dead_locals(blocks_by_id, order, function["parameters"])
    function = dict(function)
    function["blocks"] = [blocks_by_id[block_id] for block_id in order]
    return function


def _fold_block(block: dict[str, Any]) -> dict[str, Any]:
    block = dict(block)
    instructions, _ = _local_cse(
        [_fold_instruction(instruction) for instruction in block["instructions"]]
    )
    block["instructions"] = instructions
    block["terminator"] = _fold_terminator(block["terminator"])
    return block


def _fold_instruction(instruction: dict[str, Any]) -> dict[str, Any]:
    instruction = dict(instruction)
    for key in ("expr", "collection", "index", "object"):
        if key in instruction:
            instruction[key] = _fold_expr(instruction[key])
    return instruction


def _fold_terminator(terminator: dict[str, Any]) -> dict[str, Any]:
    terminator = dict(terminator)
    if "condition" in terminator:
        terminator["condition"] = _fold_expr(terminator["condition"])
    if "value" in terminator:
        terminator["value"] = _fold_expr(terminator["value"])
    return terminator


def _const(kind: str, value: Any) -> dict[str, Any]:
    return {"op": "const", "kind": kind, "value": value}


def _is_const(expr: dict[str, Any]) -> bool:
    return expr.get("op") == "const"


def _fold_expr(expr: dict[str, Any]) -> dict[str, Any]:
    op = expr.get("op")
    if op in ("const", "local"):
        return expr
    if op == "array":
        return {**expr, "elements": [_fold_expr(item) for item in expr["elements"]]}
    if op == "struct":
        return {**expr, "fields": {name: _fold_expr(value) for name, value in expr["fields"].items()}}
    if op == "unary":
        operand = _fold_expr(expr["operand"])
        if _is_const(operand):
            value = operand["value"]
            if expr["operator"] == "Negate" and isinstance(value, (int, float)) and not isinstance(value, bool):
                return _const(operand["kind"], -value)
            if expr["operator"] == "Not" and isinstance(value, bool):
                return _const("bool", not value)
        return {**expr, "operand": operand}
    if op == "binary":
        left = _fold_expr(expr["left"])
        right = _fold_expr(expr["right"])
        if _is_const(left) and _is_const(right) and _numeric(left) and _numeric(right):
            fold = _BINARY_FOLD.get(expr["operator"])
            if fold is not None:
                try:
                    value = fold(left["value"], right["value"])
                except ZeroDivisionError:
                    # Leave unfolded: the runtime raises RT-ARITH-001 at
                    # the right place instead of the optimizer having to
                    # encode "folds to an error".
                    return {**expr, "left": left, "right": right}
                kind = "float" if expr["operator"] == "Divide" else left["kind"]
                return _const(kind, value)
        return {**expr, "left": left, "right": right}
    if op == "comparison":
        left = _fold_expr(expr["left"])
        right = _fold_expr(expr["right"])
        if _is_const(left) and _is_const(right):
            fold = _COMPARISON_FOLD.get(expr["operator"])
            if fold is not None:
                return _const("bool", fold(left["value"], right["value"]))
        return {**expr, "left": left, "right": right}
    if op == "logical":
        left = _fold_expr(expr["left"])
        # Short-circuit: if the left side is already a constant that
        # decides the result, the right side doesn't need folding for
        # correctness, but folding it anyway keeps a full pre-pass over
        # the tree cheap and simple; it's discarded when short-circuited.
        right = _fold_expr(expr["right"])
        if _is_const(left) and isinstance(left["value"], bool):
            if expr["operator"] == "And" and left["value"] is False:
                return _const("bool", False)
            if expr["operator"] == "Or" and left["value"] is True:
                return _const("bool", True)
            if _is_const(right) and isinstance(right["value"], bool):
                combined = left["value"] and right["value"] if expr["operator"] == "And" else left["value"] or right["value"]
                return _const("bool", combined)
        return {**expr, "left": left, "right": right}
    if op == "index":
        # Arrays are always "array" nodes, never `const` (there is no
        # const-array literal in this IR), so there is no constant
        # collection/index combination to fold here -- just recurse.
        return {**expr, "collection": _fold_expr(expr["collection"]), "index": _fold_expr(expr["index"])}
    if op == "member":
        return {**expr, "object": _fold_expr(expr["object"])}
    if op == "call_tensor":
        return {**expr, "arguments": [_fold_expr(argument) for argument in expr["arguments"]]}
    if op == "call_vision":
        return {**expr, "arguments": [_fold_expr(argument) for argument in expr["arguments"]]}
    if op == "call_array_append":
        return {**expr, "collection": _fold_expr(expr["collection"]), "item": _fold_expr(expr["item"])}
    if op == "call_function":
        return {**expr, "arguments": [_fold_expr(argument) for argument in expr["arguments"]]}
    if op == "call_cast":
        argument = _fold_expr(expr["argument"])
        if _is_const(argument) and _numeric(argument):
            value = float(argument["value"]) if expr["name"] == "float" else int(argument["value"])
            return _const("float" if expr["name"] == "float" else "int", value)
        return {**expr, "argument": argument}
    return expr


def _numeric(const_expr: dict[str, Any]) -> bool:
    return const_expr.get("kind") in ("int", "float") and isinstance(const_expr.get("value"), (int, float))


def _simplify_branches(blocks_by_id: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for block_id, block in blocks_by_id.items():
        terminator = block["terminator"]
        if terminator["kind"] == "branch" and _is_const(terminator["condition"]):
            target = terminator["then"] if terminator["condition"]["value"] else terminator["else"]
            block = dict(block)
            block["terminator"] = {"kind": "jump", "target": target}
        result[block_id] = block
    return result


def _reachable_block_ids(blocks_by_id: dict[str, dict[str, Any]], entry: str) -> set[str]:
    seen: set[str] = set()
    stack = [entry]
    while stack:
        block_id = stack.pop()
        if block_id in seen or block_id not in blocks_by_id:
            continue
        seen.add(block_id)
        terminator = blocks_by_id[block_id]["terminator"]
        if terminator["kind"] == "jump":
            stack.append(terminator["target"])
        elif terminator["kind"] == "branch":
            stack.append(terminator["then"])
            stack.append(terminator["else"])
    return seen


def _eliminate_dead_locals(
    blocks_by_id: dict[str, dict[str, Any]], order: list[str], parameters: list[str]
) -> dict[str, dict[str, Any]]:
    del parameters  # parameters are always "used" by definition; nothing to do with them here
    read_names: set[str] = set()
    for block_id in order:
        block = blocks_by_id[block_id]
        for instruction in block["instructions"]:
            for key in ("expr", "collection", "index", "object"):
                if key in instruction:
                    _collect_reads(instruction[key], read_names)
        terminator = block["terminator"]
        if "condition" in terminator:
            _collect_reads(terminator["condition"], read_names)
        if "value" in terminator:
            _collect_reads(terminator["value"], read_names)

    result = {}
    for block_id, block in blocks_by_id.items():
        kept = []
        for instruction in block["instructions"]:
            if (
                instruction["op"] == "assign"
                and instruction["target"] not in read_names
                and _is_side_effect_free(instruction["expr"])
            ):
                continue
            kept.append(instruction)
        new_block = dict(block)
        new_block["instructions"] = kept
        result[block_id] = new_block
    return result


def _collect_reads(expr: dict[str, Any], out: set[str]) -> None:
    op = expr.get("op")
    if op == "local":
        out.add(expr["name"])
        return
    if op == "array":
        for item in expr["elements"]:
            _collect_reads(item, out)
        return
    if op == "struct":
        for value in expr["fields"].values():
            _collect_reads(value, out)
        return
    if op == "unary":
        _collect_reads(expr["operand"], out)
        return
    if op in ("binary", "comparison", "logical"):
        _collect_reads(expr["left"], out)
        _collect_reads(expr["right"], out)
        return
    if op == "index":
        _collect_reads(expr["collection"], out)
        _collect_reads(expr["index"], out)
        return
    if op == "member":
        _collect_reads(expr["object"], out)
        return
    if op in ("call_tensor", "call_vision", "call_function"):
        for argument in expr["arguments"]:
            _collect_reads(argument, out)
        return
    if op == "call_array_append":
        _collect_reads(expr["collection"], out)
        _collect_reads(expr["item"], out)
        return
    if op == "call_cast":
        _collect_reads(expr["argument"], out)
        return


_IMPURE_FUNCTION_IDS = {"tensor.load", "tensor.save"}


def _is_side_effect_free(expr: dict[str, Any]) -> bool:
    op = expr.get("op")
    if op == "call_tensor":
        if expr["function_id"] in _IMPURE_FUNCTION_IDS:
            return False
        return all(_is_side_effect_free(argument) for argument in expr["arguments"])
    if op == "call_vision":
        return False  # unknown side-effect surface; never eliminate
    if op == "call_function":
        return False  # a user function's body may call tensor.save; conservative
    if op == "call_array_append":
        return _is_side_effect_free(expr["collection"]) and _is_side_effect_free(expr["item"])
    if op == "call_cast":
        return _is_side_effect_free(expr["argument"])
    if op == "array":
        return all(_is_side_effect_free(item) for item in expr["elements"])
    if op == "struct":
        return all(_is_side_effect_free(value) for value in expr["fields"].values())
    if op == "unary":
        return _is_side_effect_free(expr["operand"])
    if op in ("binary", "comparison", "logical"):
        return _is_side_effect_free(expr["left"]) and _is_side_effect_free(expr["right"])
    if op == "index":
        return _is_side_effect_free(expr["collection"]) and _is_side_effect_free(expr["index"])
    if op == "member":
        return _is_side_effect_free(expr["object"])
    return True  # const, local


def _expr_key(expr: dict[str, Any]) -> str:
    """Canonical string key for structural equality, used by local CSE."""
    import json

    return json.dumps(expr, sort_keys=True)


def _local_cse(instructions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """CSE within one straight-line instruction list (no branches).

    `available` maps an expression's structural key to the name of a
    local already proven to hold that exact value. Before processing
    each `assign`, every cached entry whose expression reads the
    about-to-be-overwritten target is invalidated (that local's value is
    changing, so any expression computed from its *old* value is no
    longer reproducible by reading it now). A self-referential assign
    (`x = x + 1`) is looked up against the cache normally but never
    itself cached: "x" now holds "old x + 1", which is not what the
    syntactic expression `x + 1` means going forward (that will mean
    "current x + 1", a different value each time) -- caching it would
    make a later, syntactically identical `x + 1` wrongly collapse to
    plain `x`.
    """
    available: dict[str, tuple[dict[str, Any], str]] = {}
    result: list[dict[str, Any]] = []
    for instruction in instructions:
        if instruction["op"] != "assign":
            result.append(instruction)
            continue
        target = instruction["target"]
        expr = instruction["expr"]

        stale_keys = [key for key, (cached_expr, _) in available.items() if _reads_name(cached_expr, target)]
        for key in stale_keys:
            del available[key]

        if _is_cse_eligible(expr):
            key = _expr_key(expr)
            cached = available.get(key)
            if cached is not None:
                instruction = {**instruction, "expr": {"op": "local", "name": cached[1]}}
                result.append(instruction)
                continue
            reads: set[str] = set()
            _collect_reads(expr, reads)
            if target not in reads:
                available[key] = (expr, target)
        result.append(instruction)
    return result, {key: name for key, (_, name) in available.items()}


def _reads_name(expr: dict[str, Any], name: str) -> bool:
    reads: set[str] = set()
    _collect_reads(expr, reads)
    return name in reads


def _is_cse_eligible(expr: dict[str, Any]) -> bool:
    op = expr.get("op")
    if op in ("call_tensor", "call_vision", "call_function", "call_array_append"):
        return False  # never dedupe calls: see module docstring
    if op == "const" or op == "local":
        return True
    if op == "array":
        return all(_is_cse_eligible(item) for item in expr["elements"])
    if op == "struct":
        return all(_is_cse_eligible(value) for value in expr["fields"].values())
    if op == "unary":
        return _is_cse_eligible(expr["operand"])
    if op in ("binary", "comparison", "logical"):
        return _is_cse_eligible(expr["left"]) and _is_cse_eligible(expr["right"])
    if op == "index":
        return _is_cse_eligible(expr["collection"]) and _is_cse_eligible(expr["index"])
    if op == "member":
        return _is_cse_eligible(expr["object"])
    if op == "call_cast":
        return _is_cse_eligible(expr["argument"])
    return False
