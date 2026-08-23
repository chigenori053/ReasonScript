"""AST -> reason-computation-ir/0.1 basic-block lowering.

Implements the Phase 2 "AST→basic block lowering" item from the
ReasonScript modernization plan. Scope is bounded to exactly what
`frontend.integrated_computation_runtime` (the existing AST evaluator)
supports, since that is the oracle this IR is differentially tested
against (`frontend.computation_ir.differential`); constructs it doesn't
handle (pattern matching, Optional/Some, map/set literals, vision/ruo
calls, reason_object graph queries, runtime.search/simulate/predict/plan)
raise `LoweringError` rather than being silently mishandled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from frontend.language_surface.nodes import (
    ArrayLiteralNode,
    AssignmentStatementNode,
    BinaryExpressionNode,
    BooleanLiteralNode,
    BreakStatementNode,
    CalculationNode,
    CallExpressionNode,
    ComparisonExpressionNode,
    ConstStatementNode,
    ContinueStatementNode,
    ExpressionNode,
    ExpressionStatementNode,
    FieldAssignmentStatementNode,
    FloatLiteralNode,
    ForStatementNode,
    FunctionDeclarationNode,
    IdentifierNode,
    IfStatementNode,
    IndexAccessNode,
    IndexAssignmentStatementNode,
    IntegerLiteralNode,
    LetStatementNode,
    LogicalExpressionNode,
    LoopStatementNode,
    MemberAccessNode,
    NoneLiteralNode,
    NullLiteralNode,
    ParenthesizedExpressionNode,
    ProgramNode,
    ResultStatementNode,
    ReturnStatementNode,
    StringLiteralNode,
    StructLiteralNode,
    UnaryExpressionNode,
    WhileStatementNode,
)
from frontend.relation.integration import relation_call_name
from frontend.tensor.integration import tensor_call_name
from frontend.tensor.optimizers import optimizer_call_name
from frontend.vision.integration import vision_call_name

from .schema import SCHEMA

_SCALAR_CAST_NAMES = {"float", "int"}


class LoweringError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def lower_program(program: ProgramNode) -> dict[str, Any]:
    """Lower every function and calculation in every module to IR Functions.

    Returns a `reason-computation-ir/0.1` Program document (plain dict).
    Calculation bodies are lowered in module order, each into its own
    Function whose id is the calculation name (mirroring the scoping the
    AST evaluator already uses, e.g. `f"fn.{name}"` for user functions).
    """
    functions: list[dict[str, Any]] = []
    calculation_ids: list[str] = []
    for module in program.modules:
        declared_function_nodes = tuple(
            item for item in module.body if isinstance(item, FunctionDeclarationNode)
        )
        # Scoped per module, mirroring integrated_computation_runtime.py's
        # `functions` dict, which is likewise rebuilt per module: a bare
        # `float`/`int` call only resolves to the builtin cast when it
        # isn't shadowed by a `fn float`/`fn int` declared in this module.
        declared_function_names = frozenset(item.name for item in declared_function_nodes)
        for item in declared_function_nodes:
            functions.append(
                _lower_function(f"fn.{item.name}", item.parameters, item.body, declared_function_names)
            )
        for item in module.body:
            if isinstance(item, CalculationNode):
                functions.append(
                    _lower_function(item.name, (), item.body, declared_function_names)
                )
                calculation_ids.append(item.name)
    return {
        "schema": SCHEMA,
        "package": program.package.name if program.package is not None else None,
        "calculations": calculation_ids,
        "functions": functions,
        "tensor_contract_version": "0.2",
    }


def _lower_function(
    function_id: str,
    parameters: tuple[Any, ...],
    body: tuple[Any, ...],
    declared_functions: frozenset,
) -> dict[str, Any]:
    builder = _BlockBuilder(function_id, declared_functions=declared_functions)
    entry = builder.new_block("entry")
    builder.enter(entry)
    _lower_statements(body, builder, loop=None)
    if builder.current_terminator() is None:
        # Falling off the end without `result`/`return` is a distinct
        # outcome from either: for a calculation it's not an error (the
        # AST evaluator just never assigns anything to `calculations[name]`
        # in that case), but for a plain function it must become
        # RT-CALL-004. The IR itself can't tell which kind of Function
        # this is, so it reports this as a well-known trap code and lets
        # the interpreter's caller (calculation loop vs. call_function)
        # decide what it means.
        builder.terminate({
            "kind": "trap",
            "code": "IR-NO-VALUE",
            "message": f"{function_id} completed without result/return",
        })
    return {
        "id": function_id,
        "parameters": [_parameter_name(parameter) for parameter in parameters],
        "entry_block": entry,
        "blocks": builder.finish(),
    }


def _parameter_name(parameter: Any) -> str:
    return parameter["name"] if isinstance(parameter, dict) else str(parameter)


@dataclass
class _LoopTargets:
    continue_target: str
    break_target: str


@dataclass
class _BlockBuilder:
    function_id: str
    blocks: dict[str, dict[str, Any]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    counter: int = 0
    current_id: str | None = None
    declared_functions: frozenset = field(default_factory=frozenset)

    def new_block(self, hint: str) -> str:
        self.counter += 1
        block_id = f"{self.function_id}.{hint}_{self.counter}"
        self.blocks[block_id] = {"id": block_id, "instructions": [], "terminator": None}
        self.order.append(block_id)
        return block_id

    def enter(self, block_id: str) -> None:
        self.current_id = block_id

    def current_terminator(self) -> Any:
        return self.blocks[self.current_id]["terminator"]

    def emit(self, instruction: dict[str, Any]) -> None:
        if self.current_terminator() is not None:
            return  # dead code after a terminator-producing statement
        self.blocks[self.current_id]["instructions"].append(instruction)

    def terminate(self, terminator: dict[str, Any]) -> None:
        if self.current_terminator() is not None:
            return
        self.blocks[self.current_id]["terminator"] = terminator

    def jump_to(self, block_id: str) -> None:
        self.terminate({"kind": "jump", "target": block_id})

    def finish(self) -> list[dict[str, Any]]:
        for block_id in self.order:
            if self.blocks[block_id]["terminator"] is None:
                # Unreachable/empty tail block (e.g. after an if/else
                # where every branch already terminated): give it a Trap
                # so the interpreter never falls off the end silently.
                self.blocks[block_id]["terminator"] = {
                    "kind": "trap",
                    "code": "IR-UNREACHABLE",
                    "message": "block has no terminator",
                }
        return [self.blocks[block_id] for block_id in self.order]


def _lower_statements(
    statements: tuple[Any, ...],
    builder: _BlockBuilder,
    *,
    loop: _LoopTargets | None,
) -> None:
    for statement in statements:
        if builder.current_terminator() is not None:
            return  # rest of this statement list is unreachable
        _lower_statement(statement, builder, loop=loop)


def _lower_statement(statement: Any, builder: _BlockBuilder, *, loop: _LoopTargets | None) -> None:
    declared_functions = builder.declared_functions
    if isinstance(statement, (LetStatementNode, ConstStatementNode)):
        builder.emit({
            "op": "assign",
            "target": statement.identifier,
            "expr": _lower_expression(statement.expression, declared_functions),
        })
        return
    if isinstance(statement, AssignmentStatementNode):
        builder.emit({
            "op": "assign",
            "target": statement.target,
            "expr": _lower_expression(statement.expression, declared_functions),
        })
        return
    if isinstance(statement, IndexAssignmentStatementNode):
        target = _unwrap(statement.target)
        if not isinstance(target, IndexAccessNode):
            raise LoweringError("IR-LOWER-001", "invalid index assignment target")
        builder.emit({
            "op": "index_assign",
            "collection": _lower_expression(target.collection, declared_functions),
            "index": _lower_expression(target.index, declared_functions),
            "expr": _lower_expression(statement.expression, declared_functions),
        })
        return
    if isinstance(statement, FieldAssignmentStatementNode):
        target = _unwrap(statement.target)
        if not isinstance(target, MemberAccessNode):
            raise LoweringError("IR-LOWER-002", "invalid field assignment target")
        builder.emit({
            "op": "field_assign",
            "object": _lower_expression(target.object, declared_functions),
            "member": target.member,
            "expr": _lower_expression(statement.expression, declared_functions),
        })
        return
    if isinstance(statement, ResultStatementNode):
        builder.terminate({"kind": "result", "value": _lower_expression(statement.expression, declared_functions)})
        return
    if isinstance(statement, ReturnStatementNode):
        builder.terminate({"kind": "return", "value": _lower_expression(statement.expression, declared_functions)})
        return
    if isinstance(statement, ExpressionStatementNode):
        builder.emit({"op": "expr", "expr": _lower_expression(statement.expression, declared_functions)})
        return
    if isinstance(statement, BreakStatementNode):
        if loop is None:
            raise LoweringError("IR-LOWER-003", "break outside of a loop")
        builder.jump_to(loop.break_target)
        return
    if isinstance(statement, ContinueStatementNode):
        if loop is None:
            raise LoweringError("IR-LOWER-004", "continue outside of a loop")
        builder.jump_to(loop.continue_target)
        return
    if isinstance(statement, IfStatementNode):
        _lower_if(statement, builder, loop=loop)
        return
    if isinstance(statement, WhileStatementNode):
        _lower_while(statement, builder, loop=loop)
        return
    if isinstance(statement, LoopStatementNode):
        _lower_loop(statement, builder)
        return
    if isinstance(statement, ForStatementNode):
        _lower_for(statement, builder)
        return
    raise LoweringError("IR-LOWER-005", f"unsupported statement: {type(statement).__name__}")


def _lower_if(statement: IfStatementNode, builder: _BlockBuilder, *, loop: _LoopTargets | None) -> None:
    declared_functions = builder.declared_functions
    merge = builder.new_block("if_merge")
    branches = [(statement.condition, statement.body)]
    branches.extend((branch.condition, branch.body) for branch in statement.elif_branches)

    def lower_chain(index: int) -> None:
        if index >= len(branches):
            # `builder`'s current block is already the block the previous
            # branch's `else` edge points to (either `next_block` from the
            # last iteration, or the entry block if there were no
            # elif/else at all) -- lower the else body directly into it
            # rather than creating a fresh, never-entered block.
            if statement.else_branch is not None:
                _lower_statements(statement.else_branch.body, builder, loop=loop)
                if builder.current_terminator() is None:
                    builder.jump_to(merge)
            else:
                builder.jump_to(merge)
            return
        condition, body = branches[index]
        then_block = builder.new_block("then")
        next_block = builder.new_block("elif_check") if index + 1 < len(branches) or statement.else_branch is not None else merge
        builder.terminate({
            "kind": "branch",
            "condition": _lower_expression(condition, declared_functions),
            "then": then_block,
            "else": next_block,
        })
        builder.enter(then_block)
        _lower_statements(body, builder, loop=loop)
        if builder.current_terminator() is None:
            builder.jump_to(merge)
        if next_block != merge:
            builder.enter(next_block)
            lower_chain(index + 1)

    entry_needs_jump = builder.current_terminator() is not None
    if entry_needs_jump:
        return
    lower_chain(0)
    builder.enter(merge)


def _lower_while(statement: WhileStatementNode, builder: _BlockBuilder, *, loop: _LoopTargets | None) -> None:
    declared_functions = builder.declared_functions
    cond_block = builder.new_block("while_cond")
    body_block = builder.new_block("while_body")
    after_block = builder.new_block("while_after")
    builder.jump_to(cond_block)
    builder.enter(cond_block)
    builder.terminate({
        "kind": "branch",
        "condition": _lower_expression(statement.condition, declared_functions),
        "then": body_block,
        "else": after_block,
    })
    builder.enter(body_block)
    _lower_statements(
        statement.body, builder, loop=_LoopTargets(cond_block, after_block)
    )
    if builder.current_terminator() is None:
        builder.jump_to(cond_block)
    builder.enter(after_block)


def _lower_loop(statement: LoopStatementNode, builder: _BlockBuilder) -> None:
    body_block = builder.new_block("loop_body")
    after_block = builder.new_block("loop_after")
    builder.jump_to(body_block)
    builder.enter(body_block)
    _lower_statements(
        statement.body, builder, loop=_LoopTargets(body_block, after_block)
    )
    if builder.current_terminator() is None:
        builder.jump_to(body_block)
    builder.enter(after_block)


def _lower_for(statement: ForStatementNode, builder: _BlockBuilder) -> None:
    declared_functions = builder.declared_functions
    values_local = f"__for_values_{builder.counter + 1}__"
    index_local = f"__for_index_{builder.counter + 1}__"
    builder.emit({"op": "assign", "target": values_local, "expr": _lower_expression(statement.iterable, declared_functions)})
    builder.emit({"op": "assign", "target": index_local, "expr": {"op": "const", "kind": "int", "value": 0}})

    cond_block = builder.new_block("for_cond")
    body_block = builder.new_block("for_body")
    increment_block = builder.new_block("for_increment")
    after_block = builder.new_block("for_after")

    builder.jump_to(cond_block)
    builder.enter(cond_block)
    length_expr = {"op": "member", "object": {"op": "local", "name": values_local}, "member": "length"}
    condition = {
        "op": "comparison",
        "operator": "LessThan",
        "left": {"op": "local", "name": index_local},
        "right": length_expr,
    }
    builder.terminate({"kind": "branch", "condition": condition, "then": body_block, "else": after_block})

    builder.enter(body_block)
    builder.emit({
        "op": "assign",
        "target": statement.iterator,
        "expr": {
            "op": "index",
            "collection": {"op": "local", "name": values_local},
            "index": {"op": "local", "name": index_local},
        },
    })
    _lower_statements(
        statement.body, builder, loop=_LoopTargets(increment_block, after_block)
    )
    if builder.current_terminator() is None:
        builder.jump_to(increment_block)

    builder.enter(increment_block)
    builder.emit({
        "op": "assign",
        "target": index_local,
        "expr": {
            "op": "binary",
            "operator": "Add",
            "left": {"op": "local", "name": index_local},
            "right": {"op": "const", "kind": "int", "value": 1},
        },
    })
    builder.jump_to(cond_block)
    builder.enter(after_block)


def _unwrap(value: Any) -> Any:
    return value.expression if isinstance(value, ExpressionNode) else value


def _lower_expression(value: Any, declared_functions: frozenset) -> dict[str, Any]:
    value = _unwrap(value)
    source_span = getattr(value, "_source_location", None)

    def spanned(node: dict[str, Any]) -> dict[str, Any]:
        if source_span is not None:
            node["source_span"] = source_span
        return node

    if isinstance(value, IntegerLiteralNode):
        return spanned({"op": "const", "kind": "int", "value": value.value})
    if isinstance(value, FloatLiteralNode):
        return spanned({"op": "const", "kind": "float", "value": value.value})
    if isinstance(value, BooleanLiteralNode):
        return spanned({"op": "const", "kind": "bool", "value": value.value})
    if isinstance(value, StringLiteralNode):
        return spanned({"op": "const", "kind": "string", "value": value.value})
    if isinstance(value, (NoneLiteralNode, NullLiteralNode)):
        return spanned({"op": "const", "kind": "null", "value": None})
    if isinstance(value, IdentifierNode):
        return spanned({"op": "local", "name": value.name})
    if isinstance(value, ArrayLiteralNode):
        return spanned({"op": "array", "elements": [_lower_expression(item, declared_functions) for item in value.elements]})
    if isinstance(value, StructLiteralNode):
        return spanned({
            "op": "struct",
            "type_name": value.type_name,
            "fields": {field.name: _lower_expression(field.expression, declared_functions) for field in value.fields},
        })
    if isinstance(value, ParenthesizedExpressionNode):
        return _lower_expression(value.expression, declared_functions)
    if isinstance(value, UnaryExpressionNode):
        return spanned({
            "op": "unary",
            "operator": value.operator.value,
            "operand": _lower_expression(value.operand, declared_functions),
        })
    if isinstance(value, BinaryExpressionNode):
        return spanned({
            "op": "binary",
            "operator": value.operator.value,
            "left": _lower_expression(value.left, declared_functions),
            "right": _lower_expression(value.right, declared_functions),
        })
    if isinstance(value, ComparisonExpressionNode):
        return spanned({
            "op": "comparison",
            "operator": value.operator.value,
            "left": _lower_expression(value.left, declared_functions),
            "right": _lower_expression(value.right, declared_functions),
        })
    if isinstance(value, LogicalExpressionNode):
        return spanned({
            "op": "logical",
            "operator": value.operator.value,
            "left": _lower_expression(value.left, declared_functions),
            "right": _lower_expression(value.right, declared_functions),
        })
    if isinstance(value, IndexAccessNode):
        return spanned({
            "op": "index",
            "collection": _lower_expression(value.collection, declared_functions),
            "index": _lower_expression(value.index, declared_functions),
        })
    if isinstance(value, MemberAccessNode):
        return spanned({
            "op": "member",
            "object": _lower_expression(value.object, declared_functions),
            "member": value.member,
        })
    if isinstance(value, CallExpressionNode):
        return spanned(_lower_call(value, declared_functions))
    raise LoweringError("IR-LOWER-006", f"unsupported expression: {type(value).__name__}")


def _lower_call(value: CallExpressionNode, declared_functions: frozenset) -> dict[str, Any]:
    vision_function = vision_call_name(value)
    if vision_function is not None:
        return {
            "op": "call_vision",
            "function_id": vision_function,
            "arguments": [_lower_expression(argument, declared_functions) for argument in value.arguments],
        }
    tensor_function = tensor_call_name(value)
    if tensor_function is not None:
        return {
            "op": "call_tensor",
            "function_id": tensor_function,
            "arguments": [_lower_expression(argument, declared_functions) for argument in value.arguments],
        }
    optimizer_function = optimizer_call_name(value)
    if optimizer_function is not None:
        return {
            "op": "call_optimizer",
            "function_id": optimizer_function,
            "arguments": [_lower_expression(argument, declared_functions) for argument in value.arguments],
        }
    relation_function = relation_call_name(value)
    if relation_function is not None:
        return {
            "op": "call_relation",
            "function_id": relation_function,
            "arguments": [_lower_expression(argument, declared_functions) for argument in value.arguments],
        }
    if (
        isinstance(value.callee, MemberAccessNode)
        and isinstance(value.callee.object, IdentifierNode)
        and value.callee.object.name == "array"
        and value.callee.member == "append"
    ):
        if len(value.arguments) != 2:
            raise LoweringError("IR-LOWER-007", "array.append expects two arguments")
        return {
            "op": "call_array_append",
            "collection": _lower_expression(value.arguments[0], declared_functions),
            "item": _lower_expression(value.arguments[1], declared_functions),
        }
    if (
        isinstance(value.callee, IdentifierNode)
        and value.callee.name in _SCALAR_CAST_NAMES
        and value.callee.name not in declared_functions
    ):
        if len(value.arguments) != 1:
            raise LoweringError("IR-LOWER-008", f"{value.callee.name}() expects exactly one argument")
        return {
            "op": "call_cast",
            "name": value.callee.name,
            "argument": _lower_expression(value.arguments[0], declared_functions),
        }
    if isinstance(value.callee, IdentifierNode):
        return {
            "op": "call_function",
            "name": value.callee.name,
            "arguments": [_lower_expression(argument, declared_functions) for argument in value.arguments],
        }
    raise LoweringError("IR-LOWER-009", "unsupported call target")
