"""Temporary Python interpreter for reason-computation-ir/0.1.

Implements the Phase 2 "一時的なPython IR interpreter" item: walks the
basic-block IR produced by `frontend.computation_ir.lowering` and
executes it, reusing the same `TensorRuntime` / `VisionRuntimeBridge` /
error types as `frontend.integrated_computation_runtime` (the AST
evaluator) so the two can be differentially tested
(`frontend.computation_ir.differential`) and, eventually, retired in
favor of a Rust computation runtime consuming the same IR.

This interpreter is explicitly NOT meant to be the long-term execution
path — it exists to prove the IR is a faithful, executable
representation of the language subset it covers before any Rust work
begins, per the plan's "意味互換性の確立とは高速化とは別ゲート" principle
(section 1): this makes semantic equivalence checkable, it does not make
anything faster.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from frontend.integrated_computation_runtime import (
    IntegratedComputationResult,
    IntegratedRuntimeError,
    LoopLimitError,
    OPTIONAL_NONE,
    RuntimeEnumValue,
    RuntimeOptionalSome,
    RuntimeStruct,
    _index_value,
    _trace_env,
    call_relation,
)
from frontend.reason_object_runtime import ReasonObjectRuntimeError, call_ruo, load_reason_object
from frontend.reasoning_reference import ReasoningReferenceError, call_reasoning
from frontend.tensor.runtime import TensorRuntime
from frontend.vision.runtime import VisionRuntimeBridge


class IRExecutionError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


class _IRResult(Exception):
    def __init__(self, value: Any):
        self.value = value


class _IRReturn(Exception):
    def __init__(self, value: Any):
        self.value = value


class _IRNoValue(Exception):
    pass


def interpret_program(
    ir_program: dict[str, Any],
    *,
    max_loop_iterations: int = 10_000,
    max_call_depth: int = 128,
    resource_root: Path | None = None,
    filesystem_read: bool = False,
    filesystem_write: bool = False,
) -> IntegratedComputationResult:
    runtime = TensorRuntime(
        resource_root=resource_root or Path.cwd(),
        filesystem_read=filesystem_read,
        filesystem_write=filesystem_write,
    )
    runtime.reasoning_trace = []
    vision_runtime = VisionRuntimeBridge(
        resource_root or Path.cwd(), filesystem_read=filesystem_read, filesystem_write=filesystem_write
    )
    functions = {function["id"]: function for function in ir_program["functions"]}
    object_root = (resource_root or Path.cwd()).resolve()
    global_env: dict[str, Any] = {}
    global_env.update(ir_program.get("reasoning_bindings", {}))
    for binding in ir_program.get("reason_object_bindings", []):
        try:
            global_env[binding["name"]] = load_reason_object(
                object_root / binding["source_path"], object_root,
                filesystem_read=filesystem_read,
                filesystem_write=filesystem_write,
                expected_object_id=binding.get("expected_object_id"),
            )
        except ReasonObjectRuntimeError as error:
            raise IntegratedRuntimeError(error.code, str(error)) from error
    ctx = _Context(functions, runtime, vision_runtime, max_loop_iterations, max_call_depth, global_env)

    calculations: dict[str, Any] = {}
    for calculation_id in ir_program["calculations"]:
        env = {**global_env, **calculations}
        try:
            _run_function(functions[calculation_id], env, ctx, 0)
        except _IRResult as result:
            calculations[calculation_id] = result.value
            runtime.collect(calculations)
        except _IRNoValue:
            runtime.collect(calculations)
        else:
            runtime.collect(calculations)
    value = next(reversed(calculations.values()), None) if calculations else None
    return IntegratedComputationResult(
        value, runtime, ctx.loop_trace, calculations, vision_runtime
    )


class _Context:
    __slots__ = (
        "functions", "runtime", "vision_runtime", "max_loop_iterations",
        "max_call_depth", "global_env", "loop_trace", "loop_frames",
    )

    def __init__(self, functions, runtime, vision_runtime, max_loop_iterations, max_call_depth, global_env):
        self.functions = functions
        self.runtime = runtime
        self.vision_runtime = vision_runtime
        self.max_loop_iterations = max_loop_iterations
        self.max_call_depth = max_call_depth
        self.global_env = global_env
        self.loop_trace = []
        self.loop_frames = {}


def _run_function(function_ir: dict[str, Any], env: dict[str, Any], ctx: _Context, call_depth: int) -> None:
    """Executes one IR Function's blocks until a Result/Return/error terminator fires.

    Raises `_IRResult` / `_IRReturn` to signal the outcome to the caller
    (mirroring `_Result`/`_Return` in the AST evaluator), or `_IRNoValue`
    if the function fell off the end without either — the caller decides
    whether that's acceptable (a calculation with no `result =`, which is
    not an error) or not (a plain function, RT-CALL-004).
    """
    blocks = {block["id"]: block for block in function_ir["blocks"]}
    current = function_ir["entry_block"]
    visits: dict[str, int] = {}
    while True:
        visits[current] = visits.get(current, 0) + 1
        if visits[current] > ctx.max_loop_iterations:
            raise LoopLimitError(f"loop iteration limit exceeded: {ctx.max_loop_iterations}")
        block = blocks[current]
        for instruction in block["instructions"]:
            _execute_instruction(instruction, env, ctx, call_depth)
        terminator = block["terminator"]
        kind = terminator["kind"]
        if kind == "jump":
            current = terminator["target"]
            continue
        if kind == "branch":
            condition = bool(_eval_expr(terminator["condition"], env, ctx, call_depth))
            current = terminator["then"] if condition else terminator["else"]
            continue
        if kind == "pattern_branch":
            value = _eval_expr(terminator["value"], env, ctx, call_depth)
            bindings = _match_pattern(terminator["pattern"], value)
            if bindings is not None:
                env.update(bindings)
                current = terminator["then"]
            else:
                current = terminator["else"]
            continue
        if kind == "result":
            raise _IRResult(_eval_expr(terminator["value"], env, ctx, call_depth))
        if kind == "return":
            raise _IRReturn(_eval_expr(terminator["value"], env, ctx, call_depth))
        if kind == "trap":
            if terminator["code"] == "IR-NO-VALUE":
                raise _IRNoValue()
            raise IRExecutionError(terminator["code"], terminator["message"])
        raise IRExecutionError("IR-EXEC-001", f"unknown terminator kind: {kind}")


def _execute_instruction(instruction: dict[str, Any], env: dict[str, Any], ctx: _Context, call_depth: int) -> None:
    op = instruction["op"]
    if op == "trace_loop_start":
        loop_id = instruction["loop_id"]
        counter = instruction["counter"]
        iteration = int(env[counter]) + 1
        env[counter] = iteration
        ctx.loop_frames[loop_id] = (iteration, _visible_trace_env(env))
        return
    if op == "trace_loop_end":
        loop_id = instruction["loop_id"]
        iteration, previous = ctx.loop_frames.pop(loop_id)
        ctx.loop_trace.append({
            "loop_id": loop_id,
            "iteration": iteration,
            "condition": True,
            "previous_state": previous,
            "updated_state": _visible_trace_env(env),
            "break_triggered": instruction["break_triggered"],
            "continue_triggered": instruction["continue_triggered"],
        })
        return
    if op == "assign":
        env[instruction["target"]] = _eval_expr(instruction["expr"], env, ctx, call_depth)
        return
    if op == "expr":
        _eval_expr(instruction["expr"], env, ctx, call_depth)
        return
    if op == "index_assign":
        collection = _eval_expr(instruction["collection"], env, ctx, call_depth)
        index = _eval_expr(instruction["index"], env, ctx, call_depth)
        new_value = _eval_expr(instruction["expr"], env, ctx, call_depth)
        if isinstance(collection, list):
            if isinstance(index, bool) or not isinstance(index, int):
                raise IntegratedRuntimeError("RT-INDEX-001", "array index must be int")
            if index < 0 or index >= len(collection):
                raise IntegratedRuntimeError("RT-INDEX-002", f"index out of range: {index}")
            collection[index] = new_value
            return
        if isinstance(collection, dict):
            collection[index] = new_value
            return
        raise IntegratedRuntimeError("RT-INDEX-003", "value is not mutable by index")
    if op == "field_assign":
        owner = _eval_expr(instruction["object"], env, ctx, call_depth)
        member = instruction["member"]
        new_value = _eval_expr(instruction["expr"], env, ctx, call_depth)
        if not isinstance(owner, RuntimeStruct) or member not in owner.fields:
            raise IntegratedRuntimeError("RT-FIELD-002", "invalid field assignment target")
        owner.fields[member] = new_value
        return
    raise IRExecutionError("IR-EXEC-002", f"unknown instruction op: {op}")


def _visible_trace_env(env: dict[str, Any]) -> dict[str, Any]:
    return _trace_env({
        name: value for name, value in env.items()
        if not name.startswith(("__for_", "__trace_", "__opt_"))
    })


def _match_pattern(pattern: dict[str, Any], value: Any) -> dict[str, Any] | None:
    kind = pattern["kind"]
    if kind == "wildcard":
        return {}
    if kind == "binding":
        return {pattern["name"]: value}
    if kind == "literal":
        return {} if value == pattern.get("value") else None
    if kind == "range":
        try:
            lower_ok = value >= pattern["lower"] if pattern["lower_inclusive"] else value > pattern["lower"]
            upper_ok = value <= pattern["upper"] if pattern["upper_inclusive"] else value < pattern["upper"]
        except TypeError:
            return None
        return {} if lower_ok and upper_ok else None
    if kind == "enum":
        return {} if value == RuntimeEnumValue(pattern["enum_name"], pattern["variant_name"]) else None
    if kind == "optional_none":
        return {} if value == OPTIONAL_NONE else None
    if kind == "optional_some":
        if not isinstance(value, RuntimeOptionalSome):
            return None
        return _match_pattern(pattern["pattern"], value.value)
    if kind == "struct":
        if not isinstance(value, RuntimeStruct) or value.type_name != pattern["type_name"]:
            return None
        bindings: dict[str, Any] = {}
        for name, nested_pattern in pattern["fields"].items():
            if name not in value.fields:
                return None
            nested = _match_pattern(nested_pattern, value.fields[name])
            if nested is None:
                return None
            bindings.update(nested)
        return bindings
    if kind == "or":
        for alternative in pattern["alternatives"]:
            bindings = _match_pattern(alternative, value)
            if bindings is not None:
                return bindings
        return None
    raise IRExecutionError("IR-EXEC-008", f"unknown pattern kind: {kind}")


_BINARY_OPS = {
    "Add": lambda left, right: left + right,
    "Subtract": lambda left, right: left - right,
    "Multiply": lambda left, right: left * right,
    "Divide": lambda left, right: left / right,
    "Modulo": lambda left, right: left % right,
}

_COMPARISON_OPS = {
    "Equal": lambda left, right: left == right,
    "NotEqual": lambda left, right: left != right,
    "GreaterThan": lambda left, right: left > right,
    "GreaterThanOrEqual": lambda left, right: left >= right,
    "LessThan": lambda left, right: left < right,
    "LessThanOrEqual": lambda left, right: left <= right,
}


def _eval_expr(node: dict[str, Any], env: dict[str, Any], ctx: _Context, call_depth: int) -> Any:
    op = node["op"]
    if op == "const":
        return node["value"]
    if op == "local":
        name = node["name"]
        if name not in env:
            raise IntegratedRuntimeError("RT-NAME-001", f"unknown runtime name: {name}")
        return env[name]
    if op == "array":
        return [_eval_expr(item, env, ctx, call_depth) for item in node["elements"]]
    if op == "struct":
        return RuntimeStruct(
            node["type_name"],
            {name: _eval_expr(expr, env, ctx, call_depth) for name, expr in node["fields"].items()},
        )
    if op == "enum_value":
        return RuntimeEnumValue(node["enum_name"], node["variant_name"])
    if op == "optional_some":
        return RuntimeOptionalSome(_eval_expr(node["value"], env, ctx, call_depth))
    if op == "optional_none":
        return OPTIONAL_NONE
    if op == "unary":
        operand = _eval_expr(node["operand"], env, ctx, call_depth)
        return -operand if node["operator"] == "Negate" else not operand
    if op == "binary":
        left = _eval_expr(node["left"], env, ctx, call_depth)
        right = _eval_expr(node["right"], env, ctx, call_depth)
        operator = node["operator"]
        if operator in ("Divide", "Modulo") and right == 0:
            raise IntegratedRuntimeError("RT-ARITH-001", "division or modulo by zero")
        return _BINARY_OPS[operator](left, right)
    if op == "comparison":
        left = _eval_expr(node["left"], env, ctx, call_depth)
        right = _eval_expr(node["right"], env, ctx, call_depth)
        return _COMPARISON_OPS[node["operator"]](left, right)
    if op == "logical":
        left = bool(_eval_expr(node["left"], env, ctx, call_depth))
        if node["operator"] == "And":
            return left and bool(_eval_expr(node["right"], env, ctx, call_depth))
        return left or bool(_eval_expr(node["right"], env, ctx, call_depth))
    if op == "index":
        collection = _eval_expr(node["collection"], env, ctx, call_depth)
        index = _eval_expr(node["index"], env, ctx, call_depth)
        return _index_value(collection, index, ctx.runtime)
    if op == "member":
        owner = _eval_expr(node["object"], env, ctx, call_depth)
        member = node["member"]
        if isinstance(owner, RuntimeStruct):
            if member not in owner.fields:
                raise IntegratedRuntimeError(
                    "RT-FIELD-001", f"unknown field {member} on {owner.type_name}"
                )
            return owner.fields[member]
        if isinstance(owner, dict) and member in owner:
            return owner[member]
        if isinstance(owner, (list, tuple, dict)) and member == "length":
            return len(owner)
        raise IntegratedRuntimeError("RT-FIELD-001", f"member access is unsupported: {member}")
    if op == "call_tensor":
        arguments = [_eval_expr(argument, env, ctx, call_depth) for argument in node["arguments"]]
        source_span = node.get("source_span")
        return ctx.runtime.call(node["function_id"], *arguments, _source_location=source_span)
    if op == "call_ruo":
        arguments = [_eval_expr(argument, env, ctx, call_depth) for argument in node["arguments"]]
        try:
            return call_ruo(node["function_id"], *arguments)
        except ReasonObjectRuntimeError as error:
            raise IntegratedRuntimeError(error.code, str(error)) from error
    if op == "call_optimizer":
        arguments = [_eval_expr(argument, env, ctx, call_depth) for argument in node["arguments"]]
        source_span = node.get("source_span")
        return ctx.runtime.call_optimizer(node["function_id"], *arguments, _source_location=source_span)
    if op == "call_relation":
        arguments = [_eval_expr(argument, env, ctx, call_depth) for argument in node["arguments"]]
        return call_relation(node["function_id"], *arguments)
    if op == "call_vision":
        arguments = [_eval_expr(argument, env, ctx, call_depth) for argument in node["arguments"]]
        return ctx.vision_runtime.call(node["function_id"], *arguments)
    if op == "call_reasoning":
        arguments = [_eval_expr(argument, env, ctx, call_depth) for argument in node["arguments"]]
        try:
            result, trace = call_reasoning(node["function_id"], arguments[0])
        except ReasoningReferenceError as error:
            raise IntegratedRuntimeError(error.code, str(error)) from error
        ctx.runtime.reasoning_trace.append(trace)
        return result
    if op == "call_array_append":
        collection = _eval_expr(node["collection"], env, ctx, call_depth)
        item = _eval_expr(node["item"], env, ctx, call_depth)
        if not isinstance(collection, list):
            raise IntegratedRuntimeError("RT-CALL-002", "array.append first argument must be an array")
        import copy

        return [*collection, copy.deepcopy(item)]
    if op == "call_array_concat":
        left = _eval_expr(node["left"], env, ctx, call_depth)
        right = _eval_expr(node["right"], env, ctx, call_depth)
        if not isinstance(left, list) or not isinstance(right, list):
            raise IntegratedRuntimeError("RT-CALL-002", "array.concat arguments must be arrays")
        import copy
        return [*copy.deepcopy(left), *copy.deepcopy(right)]
    if op == "call_string":
        function_id = node["function_id"]
        arguments = [_eval_expr(argument, env, ctx, call_depth) for argument in node["arguments"]]
        if function_id == "concat":
            if len(arguments) != 2 or not isinstance(arguments[0], str) or not isinstance(arguments[1], str):
                raise IntegratedRuntimeError("RT-CALL-002", "string.concat expects two string arguments")
            return arguments[0] + arguments[1]
        elif function_id == "join":
            if len(arguments) != 2 or not isinstance(arguments[0], str) or not isinstance(arguments[1], list):
                raise IntegratedRuntimeError("RT-CALL-002", "string.join expects separator string and list of strings")
            for item in arguments[1]:
                if not isinstance(item, str):
                    raise IntegratedRuntimeError("RT-CALL-002", "string.join list elements must be strings")
            return arguments[0].join(arguments[1])
        elif function_id == "length":
            if len(arguments) != 1 or not isinstance(arguments[0], str):
                raise IntegratedRuntimeError("RT-CALL-002", "string.length expects one string argument")
            return len(arguments[0])
        elif function_id == "from_int":
            if len(arguments) != 1 or isinstance(arguments[0], bool) or not isinstance(arguments[0], int):
                raise IntegratedRuntimeError("RT-CALL-002", "string.from_int expects one int argument")
            return str(arguments[0])
        elif function_id == "from_float":
            if len(arguments) != 1 or isinstance(arguments[0], bool) or not isinstance(arguments[0], (float, int)):
                raise IntegratedRuntimeError("RT-CALL-002", "string.from_float expects one float argument")
            f_val = float(arguments[0])
            return str(f_val)
        elif function_id == "slice":
            if len(arguments) != 3 or not isinstance(arguments[0], str) or isinstance(arguments[1], bool) or not isinstance(arguments[1], int) or isinstance(arguments[2], bool) or not isinstance(arguments[2], int):
                raise IntegratedRuntimeError("RT-CALL-002", "string.slice expects string, int, int")
            s, start, end = arguments[0], arguments[1], arguments[2]
            if start < 0:
                start = 0
            if end < start:
                end = start
            return s[start:end]
        else:
            raise IntegratedRuntimeError("RT-CALL-002", f"unknown string standard function: {function_id}")
    if op == "call_assert":
        cond = _eval_expr(node["condition"], env, ctx, call_depth)
        if not isinstance(cond, bool):
            raise IntegratedRuntimeError("TEST-ASSERT-001", "assert condition must evaluate to boolean")
        if not cond:
            raise IntegratedRuntimeError("TEST-ASSERT-001", "assertion failed")
        return True
    if op == "call_assert_eq":
        left = _eval_expr(node["left"], env, ctx, call_depth)
        right = _eval_expr(node["right"], env, ctx, call_depth)
        if left != right:
            raise IntegratedRuntimeError("TEST-ASSERT-001", f"assertion failed: {left} != {right}")
        return True
    if op == "call_cast":
        argument = _eval_expr(node["argument"], env, ctx, call_depth)
        if isinstance(argument, bool) or not isinstance(argument, (int, float)):
            raise IntegratedRuntimeError("RT-CALL-005", f"{node['name']}() argument must be Int or Float")
        return float(argument) if node["name"] == "float" else int(argument)
    if op == "call_function":
        return _call_function(node["name"], node["arguments"], env, ctx, call_depth)
    raise IRExecutionError("IR-EXEC-003", f"unknown expression op: {op}")


def _call_function(
    name: str, argument_nodes: list[dict[str, Any]], env: dict[str, Any], ctx: _Context, call_depth: int
) -> Any:
    function_ir = ctx.functions.get(f"fn.{name}")
    if function_ir is None:
        raise IntegratedRuntimeError("RT-CALL-001", f"unknown runtime function: {name}")
    if len(argument_nodes) != len(function_ir["parameters"]):
        raise IntegratedRuntimeError("RT-CALL-002", f"function argument count mismatch: {name}")
    if call_depth >= ctx.max_call_depth:
        raise IntegratedRuntimeError("RT-CALL-003", f"function call depth exceeded: {ctx.max_call_depth}")
    arguments = [_eval_expr(argument, env, ctx, call_depth) for argument in argument_nodes]
    local_env = {**ctx.global_env, **dict(zip(function_ir["parameters"], arguments))}
    try:
        with ctx.runtime.protect(env):
            _run_function(function_ir, local_env, ctx, call_depth + 1)
    except _IRReturn as returned:
        return returned.value
    except _IRNoValue:
        raise IntegratedRuntimeError("RT-CALL-004", f"function returned no value: {name}") from None
    raise IRExecutionError("IR-EXEC-004", f"function block fell through without a terminator: {name}")
