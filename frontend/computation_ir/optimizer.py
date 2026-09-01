"""Phase 7 "IR最適化" — optimization passes over `reason-computation-ir/0.1`.

Runs entirely on the Python side, on the same JSON `lower_program`
produces, so a single implementation benefits both consumers of the IR:
`frontend.computation_ir.interpreter` (Python) and the Rust
`reason-computation-runtime` (`ReasonRuntime/`) -- optimizing
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
  `call_ruo`/`call_optimizer`/`call_relation`/`call_reasoning`/
  `call_function`/`call_array_append`
  are treated as impure (never deduplicated) -- Tensor, Optimizer, and
  Relation calls can all raise (shape/dtype errors, or an incomparable
  field type), and a
  user function can itself contain a `tensor.save`, so CSE-ing them
  would risk skipping a side effect or an error a second occurrence
  should still raise.

The UERA-8 fast path additionally performs conservative scalar-function
inlining and loop-invariant code motion.  Unknown purity is never eligible.
LICM keeps the original assignment in the loop and hoists only its proven-total
computation into an optimizer-private temporary; runtime trace renderers hide
that temporary, preserving observable loop traces.

NOT implemented (documented, not silent): cross-block CSE, a Relation
Matrix-specific cache, gradient pruning as a *compile-time* IR pass
(the interpreter and Rust VM already only walk tape nodes reachable from
the requested loss at `grad()`-call time -- see
`ReasonRuntime/crates/tensor-core/src/autograd.rs` -- which is
this codebase's form of "don't generate a VJP that can't reach the
loss"), liveness-driven Tensor buffer reuse, and kernel fusion
(`fused softmax`/batched matmul don't apply: `softmax` isn't implemented
at all, per Phase 4's scope, and `matmul` is rank-2 / unbatched only).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
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


@dataclass(frozen=True)
class PureReasonFunction:
    """Conservative fast-path classification for one Computation IR function."""

    name: str
    instruction_count: int
    pure: bool
    recursive: bool
    inlineable_shape: bool

    @property
    def eligible_for_fast_path(self) -> bool:
        return (
            self.pure
            and not self.recursive
            and self.inlineable_shape
            and self.instruction_count <= 32
        )


def classify_pure_functions(document: dict[str, Any]) -> dict[str, PureReasonFunction]:
    """Classify functions without guessing when purity cannot be proven."""

    functions = {
        _call_name(function["id"]): function
        for function in document.get("functions", [])
        if str(function.get("id", "")).startswith("fn.")
    }
    calls = {name: _function_calls(function) for name, function in functions.items()}

    def recursive(name: str, path: tuple[str, ...] = ()) -> bool:
        if name in path:
            return True
        return any(
            callee in functions and recursive(callee, (*path, name))
            for callee in calls[name]
        )

    recursive_names = {name for name in functions if recursive(name)}
    memo: dict[str, bool] = {}

    def pure(name: str, active: frozenset[str] = frozenset()) -> bool:
        if name in memo:
            return memo[name]
        if name in active or name in recursive_names:
            return False
        function = functions[name]
        result = all(
            _instruction_is_pure(instruction, functions, pure, active | {name})
            for block in function["blocks"]
            for instruction in block["instructions"]
        ) and all(
            _terminator_is_pure(block["terminator"], functions, pure, active | {name})
            for block in function["blocks"]
        )
        memo[name] = result
        return result

    return {
        name: PureReasonFunction(
            name=name,
            instruction_count=sum(len(block["instructions"]) for block in function["blocks"]),
            pure=pure(name),
            recursive=name in recursive_names,
            inlineable_shape=_inlineable_shape(function),
        )
        for name, function in functions.items()
    }


def optimize_program(document: dict[str, Any]) -> dict[str, Any]:
    """Returns a new, optimized `reason-computation-ir/0.1` document.

    `document` is not mutated. Safe to run repeatedly (idempotent modulo
    block/local renumbering never happening -- this pass never
    introduces new ids).
    """
    optimized = copy.deepcopy(document)
    classifications = classify_pure_functions(optimized)
    templates = _inline_templates(optimized, classifications)
    optimized["functions"] = [
        _optimize_function(_inline_function(function, templates))
        for function in optimized["functions"]
    ]
    return optimized


def _optimize_function(function: dict[str, Any]) -> dict[str, Any]:
    blocks_by_id = {block["id"]: _fold_block(block) for block in function["blocks"]}
    blocks_by_id = _simplify_branches(blocks_by_id)
    order = [block["id"] for block in function["blocks"]]
    reachable = _reachable_block_ids(blocks_by_id, function["entry_block"])
    order = [block_id for block_id in order if block_id in reachable]
    blocks_by_id = _hoist_loop_invariants(blocks_by_id, order)
    blocks_by_id = _eliminate_dead_locals(blocks_by_id, order, function["parameters"])
    function = dict(function)
    function["blocks"] = [blocks_by_id[block_id] for block_id in order]
    return function


def _call_name(function_id: str) -> str:
    return function_id.removeprefix("fn.")


def _inlineable_shape(function: dict[str, Any]) -> bool:
    if len(function["blocks"]) != 1:
        return False
    block = function["blocks"][0]
    return (
        block["terminator"].get("kind") == "return"
        and all(instruction.get("op") == "assign" for instruction in block["instructions"])
    )


def _function_calls(function: dict[str, Any]) -> set[str]:
    calls: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("op") == "call_function" and isinstance(value.get("name"), str):
                calls.add(value["name"])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(function)
    return calls


def _instruction_is_pure(
    instruction: dict[str, Any],
    functions: dict[str, dict[str, Any]],
    pure,
    active: frozenset[str],
) -> bool:
    if instruction.get("op") != "assign":
        return False
    return _expr_is_pure_function_body(instruction["expr"], functions, pure, active)


def _terminator_is_pure(
    terminator: dict[str, Any],
    functions: dict[str, dict[str, Any]],
    pure,
    active: frozenset[str],
) -> bool:
    if not all(
        _expr_is_pure_function_body(terminator[key], functions, pure, active)
        for key in ("condition", "value")
        if key in terminator
    ):
        return False
    if terminator.get("kind") == "match":
        if not _expr_is_pure_function_body(terminator["subject"], functions, pure, active):
            return False
        return all(
            arm["guard"] is None
            or _expr_is_pure_function_body(arm["guard"], functions, pure, active)
            for arm in terminator["arms"]
        )
    return True


def _expr_is_pure_function_body(
    expr: dict[str, Any],
    functions: dict[str, dict[str, Any]],
    pure,
    active: frozenset[str],
) -> bool:
    op = expr.get("op")
    if op == "call_function":
        name = expr.get("name")
        return (
            isinstance(name, str)
            and name in functions
            and pure(name, active)
            and all(
                _expr_is_pure_function_body(argument, functions, pure, active)
                for argument in expr["arguments"]
            )
        )
    if op in {
        "call_tensor",
        "call_vision",
        "call_ruo",
        "call_optimizer",
        "call_relation",
        "call_reasoning",
        "call_array_append",
    }:
        return False
    return all(
        _expr_is_pure_function_body(child, functions, pure, active)
        for child in _expr_children(expr)
    )


def _expr_children(expr: dict[str, Any]) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []
    for key, value in expr.items():
        if key in {"source_span", "value"}:
            continue
        if isinstance(value, dict) and "op" in value:
            children.append(value)
        elif isinstance(value, list):
            children.extend(item for item in value if isinstance(item, dict) and "op" in item)
        elif isinstance(value, dict):
            children.extend(item for item in value.values() if isinstance(item, dict) and "op" in item)
    return children


def _inline_templates(
    document: dict[str, Any], classifications: dict[str, PureReasonFunction]
) -> dict[str, tuple[list[str], dict[str, Any]]]:
    functions = {
        _call_name(function["id"]): function
        for function in document["functions"]
        if str(function.get("id", "")).startswith("fn.")
    }
    templates: dict[str, tuple[list[str], dict[str, Any]]] = {}

    def build(name: str, active: frozenset[str] = frozenset()):
        if name in templates:
            return templates[name]
        classification = classifications.get(name)
        if classification is None or not classification.eligible_for_fast_path or name in active:
            return None
        function = functions[name]
        bindings: dict[str, dict[str, Any]] = {
            parameter: {"op": "local", "name": parameter}
            for parameter in function["parameters"]
        }
        for instruction in function["blocks"][0]["instructions"]:
            value = _substitute_expr(instruction["expr"], bindings)
            value = _inline_expr(value, templates, lambda callee: build(callee, active | {name}))
            bindings[instruction["target"]] = value
        result = _substitute_expr(function["blocks"][0]["terminator"]["value"], bindings)
        result = _inline_expr(result, templates, lambda callee: build(callee, active | {name}))
        templates[name] = (list(function["parameters"]), result)
        return templates[name]

    for name in functions:
        build(name)
    return templates


def _substitute_expr(expr: dict[str, Any], bindings: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if expr.get("op") == "local" and expr.get("name") in bindings:
        return copy.deepcopy(bindings[expr["name"]])
    result: dict[str, Any] = {}
    for key, value in expr.items():
        if isinstance(value, dict) and "op" in value:
            result[key] = _substitute_expr(value, bindings)
        elif isinstance(value, list):
            result[key] = [
                _substitute_expr(item, bindings) if isinstance(item, dict) and "op" in item else item
                for item in value
            ]
        elif isinstance(value, dict):
            result[key] = {
                name: _substitute_expr(item, bindings)
                if isinstance(item, dict) and "op" in item
                else item
                for name, item in value.items()
            }
        else:
            result[key] = value
    return result


def _safe_inline_argument(expr: dict[str, Any]) -> bool:
    op = expr.get("op")
    if op in {"const", "local"}:
        return True
    if op in {"unary", "binary", "comparison", "logical", "call_cast"}:
        return all(_safe_inline_argument(child) for child in _expr_children(expr))
    return False


def _inline_expr(expr: dict[str, Any], templates, resolver=lambda _name: None) -> dict[str, Any]:
    expr = {
        key: (
            _inline_expr(value, templates, resolver)
            if isinstance(value, dict) and "op" in value
            else [
                _inline_expr(item, templates, resolver)
                if isinstance(item, dict) and "op" in item
                else item
                for item in value
            ]
            if isinstance(value, list)
            else {
                name: _inline_expr(item, templates, resolver)
                if isinstance(item, dict) and "op" in item
                else item
                for name, item in value.items()
            }
            if isinstance(value, dict)
            else value
        )
        for key, value in expr.items()
    }
    if expr.get("op") != "call_function":
        return expr
    name = expr.get("name")
    template = templates.get(name) or resolver(name)
    arguments = expr.get("arguments", [])
    if template is None or not all(_safe_inline_argument(argument) for argument in arguments):
        return expr
    parameters, result = template
    if len(parameters) != len(arguments):
        return expr
    return _substitute_expr(result, dict(zip(parameters, arguments)))


def _inline_function(function: dict[str, Any], templates) -> dict[str, Any]:
    function = copy.deepcopy(function)
    for block in function["blocks"]:
        for instruction in block["instructions"]:
            for key in ("expr", "collection", "index", "object"):
                if key in instruction:
                    instruction[key] = _inline_expr(instruction[key], templates)
        for key in ("condition", "value"):
            if key in block["terminator"]:
                block["terminator"][key] = _inline_expr(block["terminator"][key], templates)
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
    if terminator.get("kind") == "match":
        terminator["subject"] = _fold_expr(terminator["subject"])
        terminator["arms"] = [
            {**arm, "guard": _fold_expr(arm["guard"]) if arm["guard"] is not None else None}
            for arm in terminator["arms"]
        ]
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
    if op in ("call_ruo", "call_reasoning"):
        return {**expr, "arguments": [_fold_expr(argument) for argument in expr["arguments"]]}
    if op == "call_vision":
        return {**expr, "arguments": [_fold_expr(argument) for argument in expr["arguments"]]}
    if op == "call_optimizer":
        return {**expr, "arguments": [_fold_expr(argument) for argument in expr["arguments"]]}
    if op == "call_relation":
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
    if op == "optional_some":
        return {**expr, "value": _fold_expr(expr["value"])}
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
        elif terminator["kind"] == "match":
            stack.extend(arm["target"] for arm in terminator["arms"])
    return seen


def _hoist_loop_invariants(
    blocks_by_id: dict[str, dict[str, Any]], order: list[str]
) -> dict[str, dict[str, Any]]:
    """Hoist proven-total loop computations while preserving assignment timing.

    Lowered ``while`` loops have a branch header, a body path that jumps back to
    that header, and one outside predecessor (the preheader).  The expensive
    expression moves to an optimizer-private temporary in the preheader; the
    original assignment remains in the body as ``target = temporary``.  Trace
    renderers omit optimizer-private names, so observable state is unchanged.
    """

    result = copy.deepcopy(blocks_by_id)
    predecessors = _predecessors(result)
    temp_index = 0
    for header_id in order:
        header = result[header_id]
        terminator = header["terminator"]
        if terminator.get("kind") != "branch":
            continue
        then_id = terminator["then"]
        else_id = terminator["else"]
        loop_ids = _loop_region(result, then_id, header_id, else_id)
        if not loop_ids or not _region_reaches(result, loop_ids, header_id):
            continue
        outside_predecessors = [
            predecessor
            for predecessor in predecessors.get(header_id, set())
            if predecessor not in loop_ids
        ]
        if len(outside_predecessors) != 1:
            continue
        preheader_id = outside_predecessors[0]
        mutated = {
            instruction["target"]
            for block_id in loop_ids
            for instruction in result[block_id]["instructions"]
            if instruction.get("op") == "assign"
        }
        assignment_counts = {
            name: sum(
                1
                for block_id in loop_ids
                for instruction in result[block_id]["instructions"]
                if instruction.get("op") == "assign" and instruction["target"] == name
            )
            for name in mutated
        }
        outside_reads = _reads_in_blocks(result, set(result) - loop_ids)
        hoisted: list[dict[str, Any]] = []
        for block_id in order:
            if block_id not in loop_ids:
                continue
            instructions = []
            for instruction in result[block_id]["instructions"]:
                if instruction.get("op") != "assign":
                    instructions.append(instruction)
                    continue
                target = instruction["target"]
                expr = instruction["expr"]
                reads: set[str] = set()
                _collect_reads(expr, reads)
                eligible = (
                    assignment_counts.get(target) == 1
                    and target not in outside_reads
                    and not reads.intersection(mutated)
                    and _is_speculatively_total(expr)
                    and expr.get("op") not in {"const", "local"}
                )
                if not eligible:
                    instructions.append(instruction)
                    continue
                temp_index += 1
                temporary = f"__opt_licm_{temp_index}__"
                hoisted.append({"op": "assign", "target": temporary, "expr": expr})
                instructions.append(
                    {**instruction, "expr": {"op": "local", "name": temporary}}
                )
            result[block_id]["instructions"] = instructions
        if hoisted:
            result[preheader_id]["instructions"].extend(hoisted)
    return result


def _terminator_targets(terminator: dict[str, Any]) -> list[str]:
    kind = terminator.get("kind")
    if kind == "jump":
        return [terminator["target"]]
    if kind == "branch":
        return [terminator["then"], terminator["else"]]
    if kind == "match":
        return [arm["target"] for arm in terminator["arms"]]
    return []


def _predecessors(blocks_by_id: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {block_id: set() for block_id in blocks_by_id}
    for block_id, block in blocks_by_id.items():
        for target in _terminator_targets(block["terminator"]):
            result.setdefault(target, set()).add(block_id)
    return result


def _loop_region(
    blocks_by_id: dict[str, dict[str, Any]], start: str, header: str, exit_id: str
) -> set[str]:
    region: set[str] = set()
    stack = [start]
    while stack:
        block_id = stack.pop()
        if block_id in region or block_id in {header, exit_id} or block_id not in blocks_by_id:
            continue
        region.add(block_id)
        terminator = blocks_by_id[block_id]["terminator"]
        stack.extend(_terminator_targets(terminator))
    return region


def _region_reaches(
    blocks_by_id: dict[str, dict[str, Any]], region: set[str], target: str
) -> bool:
    return any(
        block["terminator"].get("kind") == "jump"
        and block["terminator"].get("target") == target
        for block_id, block in blocks_by_id.items()
        if block_id in region
    )


def _reads_in_blocks(
    blocks_by_id: dict[str, dict[str, Any]], block_ids: set[str]
) -> set[str]:
    reads: set[str] = set()
    for block_id in block_ids:
        block = blocks_by_id[block_id]
        for instruction in block["instructions"]:
            for key in ("expr", "collection", "index", "object"):
                if key in instruction:
                    _collect_reads(instruction[key], reads)
        for key in ("condition", "value"):
            if key in block["terminator"]:
                _collect_reads(block["terminator"][key], reads)
    return reads


def _is_speculatively_total(expr: dict[str, Any]) -> bool:
    op = expr.get("op")
    if op in {"const", "local"}:
        return True
    if op == "unary":
        return _is_speculatively_total(expr["operand"])
    if op in {"comparison", "logical"}:
        return _is_speculatively_total(expr["left"]) and _is_speculatively_total(expr["right"])
    if op == "binary":
        return (
            expr.get("operator") not in {"Divide", "Modulo"}
            and _is_speculatively_total(expr["left"])
            and _is_speculatively_total(expr["right"])
        )
    return False


def _eliminate_dead_locals(
    blocks_by_id: dict[str, dict[str, Any]], order: list[str], parameters: list[str]
) -> dict[str, dict[str, Any]]:
    del parameters  # parameters are always "used" by definition; nothing to do with them here
    read_names: set[str] = set()
    for block_id in order:
        block = blocks_by_id[block_id]
        for instruction in block["instructions"]:
            if instruction.get("op") == "trace_loop_start":
                read_names.add(instruction["counter"])
            for key in ("expr", "collection", "index", "object"):
                if key in instruction:
                    _collect_reads(instruction[key], read_names)
        terminator = block["terminator"]
        if "condition" in terminator:
            _collect_reads(terminator["condition"], read_names)
        if "value" in terminator:
            _collect_reads(terminator["value"], read_names)
        if terminator.get("kind") == "match":
            _collect_reads(terminator["subject"], read_names)
            for arm in terminator["arms"]:
                if arm["guard"] is not None:
                    _collect_reads(arm["guard"], read_names)

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
    if op in ("call_tensor", "call_vision", "call_ruo", "call_optimizer", "call_relation", "call_reasoning", "call_function"):
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
    if op == "optional_some":
        _collect_reads(expr["value"], out)
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
    if op in ("call_ruo", "call_reasoning"):
        return False  # may mutate, diagnose, or emit observable trace
    if op == "call_optimizer":
        # Every `optimizer.*` function is a pure elementwise step over its
        # Tensor/scalar arguments (see frontend/tensor/optimizers.py) --
        # no load/save equivalent exists in this namespace.
        return all(_is_side_effect_free(argument) for argument in expr["arguments"])
    if op == "call_relation":
        # Every `relation.*` function is a pure read over an
        # Array<Struct> value (see frontend/relation/integration.py) --
        # no I/O or mutation.
        return all(_is_side_effect_free(argument) for argument in expr["arguments"])
    if op == "call_function":
        return False  # a user function's body may call tensor.save; conservative
    if op == "call_array_append":
        return _is_side_effect_free(expr["collection"]) and _is_side_effect_free(expr["item"])
    if op == "call_cast":
        return _is_side_effect_free(expr["argument"])
    if op == "optional_some":
        return _is_side_effect_free(expr["value"])
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
    if op in ("call_tensor", "call_vision", "call_ruo", "call_optimizer", "call_relation", "call_reasoning", "call_function", "call_array_append"):
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
    if op in ("enum_value", "optional_none"):
        return True
    if op == "optional_some":
        return _is_cse_eligible(expr["value"])
    return False
