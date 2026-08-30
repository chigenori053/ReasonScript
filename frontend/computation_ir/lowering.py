"""AST -> reason-computation-ir/0.1 basic-block lowering.

Implements the Phase 2 "AST→basic block lowering" item from the
ReasonScript modernization plan. Scope is bounded to exactly what
`frontend.integrated_computation_runtime` (the existing AST evaluator)
supports, since that is the oracle this IR is differentially tested
against (`frontend.computation_ir.differential`); constructs it doesn't
handle (map/set literals and reason_object graph queries)
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
    DefaultPatternNode,
    EnumDeclarationNode,
    EnumValuePatternNode,
    ExpressionNode,
    ExpressionStatementNode,
    FieldAssignmentStatementNode,
    FloatLiteralNode,
    ForStatementNode,
    FunctionDeclarationNode,
    GoalNode,
    IdentifierNode,
    IdentifierPatternNode,
    IfStatementNode,
    ImportNode,
    IndexAccessNode,
    IndexAssignmentStatementNode,
    IntegerLiteralNode,
    LetStatementNode,
    LogicalExpressionNode,
    LoopStatementNode,
    LiteralPatternNode,
    MatchStatementNode,
    MemberAccessNode,
    NoneLiteralNode,
    NullLiteralNode,
    OptionalPatternNode,
    OptionalValuePatternNode,
    OrPatternNode,
    ParenthesizedExpressionNode,
    ProgramNode,
    QualifiedIdentifierNode,
    QualifiedPatternNode,
    ReasonGraphDeclarationNode,
    ResultStatementNode,
    ReasonObjectBindingNode,
    RangePatternNode,
    ReturnStatementNode,
    RuntimeCallExpressionNode,
    RuntimeCallKind,
    StateDeclarationNode,
    ConstraintNode,
    ExecutionPlanDeclarationNode,
    StringLiteralNode,
    StructBindingPatternNode,
    StructPatternNode,
    StructLiteralNode,
    SomeExpressionNode,
    UnaryExpressionNode,
    WhileStatementNode,
    WildcardPatternNode,
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
    reason_object_bindings: list[dict[str, Any]] = []
    reasoning_bindings: dict[str, str] = {}
    package_name = program.package.name if program.package is not None else None
    enum_names_by_module = {
        module.name: {
            item.name for item in module.body if isinstance(item, EnumDeclarationNode)
        }
        for module in program.modules
    }
    for module in program.modules:
        reason_object_bindings.extend({
            "name": item.name,
            "source_path": item.source_path,
            "resource_root": item.resource_root,
            "load_mode": item.load_mode,
            "expected_object_id": item.expected_object_id,
        } for item in module.body if isinstance(item, ReasonObjectBindingNode))
        for item in module.body:
            if isinstance(item, (
                GoalNode,
                StateDeclarationNode,
                ConstraintNode,
                ReasonGraphDeclarationNode,
                ExecutionPlanDeclarationNode,
            )):
                reasoning_bindings[item.name] = item.name
        declared_function_nodes = tuple(
            item for item in module.body if isinstance(item, FunctionDeclarationNode)
        )
        # Scoped per module, mirroring integrated_computation_runtime.py's
        # `functions` dict, which is likewise rebuilt per module: a bare
        # `float`/`int` call only resolves to the builtin cast when it
        # isn't shadowed by a `fn float`/`fn int` declared in this module.
        module_namespace = f"{package_name}.{module.name}" if package_name else module.name
        declared_function_names = {
            item.name: f"{module_namespace}::{item.name}"
            for item in declared_function_nodes
        }
        enum_names = set(enum_names_by_module[module.name])
        for item in module.body:
            if not isinstance(item, ImportNode) or item.resolution is None:
                continue
            target_enums = enum_names_by_module.get(
                item.resolution.namespace.rsplit(".", 1)[-1], set()
            )
            if item.resolution.symbol in target_enums:
                enum_names.update(item.resolution.exposed_names)
            elif item.resolution.symbol is None:
                enum_names.update(set(item.resolution.exposed_names) & target_enums)
        for item in declared_function_nodes:
            functions.append(
                _lower_function(
                    f"fn.{declared_function_names[item.name]}",
                    item.parameters,
                    item.body,
                    declared_function_names,
                    enum_names,
                )
            )
        for item in module.body:
            if isinstance(item, CalculationNode):
                functions.append(
                    _lower_function(item.name, (), item.body, declared_function_names, enum_names)
                )
                calculation_ids.append(item.name)
    return {
        "schema": SCHEMA,
        "package": program.package.name if program.package is not None else None,
        "calculations": calculation_ids,
        "functions": functions,
        "reason_object_bindings": reason_object_bindings,
        "reasoning_bindings": reasoning_bindings,
        "tensor_contract_version": "0.2",
    }


def _lower_function(
    function_id: str,
    parameters: tuple[Any, ...],
    body: tuple[Any, ...],
    declared_functions: dict[str, str],
    enum_names: set[str],
) -> dict[str, Any]:
    trace_scope = (
        f"fn.{function_id.rsplit('::', 1)[-1]}"
        if function_id.startswith("fn.")
        else function_id
    )
    builder = _BlockBuilder(
        function_id,
        declared_functions=declared_functions,
        enum_names=enum_names,
        trace_scope=trace_scope,
    )
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
    trace_loop_id: str


@dataclass
class _BlockBuilder:
    function_id: str
    blocks: dict[str, dict[str, Any]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    counter: int = 0
    current_id: str | None = None
    declared_functions: dict[str, str] = field(default_factory=dict)
    enum_names: set[str] = field(default_factory=set)
    trace_scope: str = ""

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
    enum_names = builder.enum_names
    if isinstance(statement, (LetStatementNode, ConstStatementNode)):
        builder.emit({
            "op": "assign",
            "target": statement.identifier,
            "expr": _lower_expression(statement.expression, declared_functions, enum_names),
        })
        return
    if isinstance(statement, AssignmentStatementNode):
        builder.emit({
            "op": "assign",
            "target": statement.target,
            "expr": _lower_expression(statement.expression, declared_functions, enum_names),
        })
        return
    if isinstance(statement, IndexAssignmentStatementNode):
        target = _unwrap(statement.target)
        if not isinstance(target, IndexAccessNode):
            raise LoweringError("IR-LOWER-001", "invalid index assignment target")
        builder.emit({
            "op": "index_assign",
            "collection": _lower_expression(target.collection, declared_functions, enum_names),
            "index": _lower_expression(target.index, declared_functions, enum_names),
            "expr": _lower_expression(statement.expression, declared_functions, enum_names),
        })
        return
    if isinstance(statement, FieldAssignmentStatementNode):
        target = _unwrap(statement.target)
        if not isinstance(target, MemberAccessNode):
            raise LoweringError("IR-LOWER-002", "invalid field assignment target")
        builder.emit({
            "op": "field_assign",
            "object": _lower_expression(target.object, declared_functions, enum_names),
            "member": target.member,
            "expr": _lower_expression(statement.expression, declared_functions, enum_names),
        })
        return
    if isinstance(statement, ResultStatementNode):
        builder.terminate({"kind": "result", "value": _lower_expression(statement.expression, declared_functions, enum_names)})
        return
    if isinstance(statement, ReturnStatementNode):
        builder.terminate({"kind": "return", "value": _lower_expression(statement.expression, declared_functions, enum_names)})
        return
    if isinstance(statement, ExpressionStatementNode):
        builder.emit({"op": "expr", "expr": _lower_expression(statement.expression, declared_functions, enum_names)})
        return
    if isinstance(statement, BreakStatementNode):
        if loop is None:
            raise LoweringError("IR-LOWER-003", "break outside of a loop")
        builder.emit({"op": "trace_loop_end", "loop_id": loop.trace_loop_id, "break_triggered": True, "continue_triggered": False})
        builder.jump_to(loop.break_target)
        return
    if isinstance(statement, ContinueStatementNode):
        if loop is None:
            raise LoweringError("IR-LOWER-004", "continue outside of a loop")
        builder.emit({"op": "trace_loop_end", "loop_id": loop.trace_loop_id, "break_triggered": False, "continue_triggered": True})
        builder.jump_to(loop.continue_target)
        return
    if isinstance(statement, IfStatementNode):
        _lower_if(statement, builder, loop=loop)
        return
    if isinstance(statement, MatchStatementNode):
        _lower_match(statement, builder, loop=loop)
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


def _lower_match(
    statement: MatchStatementNode,
    builder: _BlockBuilder,
    *,
    loop: _LoopTargets | None,
) -> None:
    subject_local = f"__match_subject_{builder.counter + 1}__"
    builder.emit({
        "op": "assign",
        "target": subject_local,
        "expr": _lower_expression(statement.expression, builder.declared_functions, builder.enum_names),
    })
    merge: str | None = None

    for index, arm in enumerate(statement.arms):
        matched = builder.new_block("match_arm")
        unmatched = builder.new_block("match_next")
        builder.terminate({
            "kind": "pattern_branch",
            "value": {"op": "local", "name": subject_local},
            "pattern": _lower_pattern(arm.pattern.pattern),
            "then": matched,
            "else": unmatched,
        })
        builder.enter(matched)
        if arm.guard is not None:
            guarded_body = builder.new_block("match_guarded_body")
            builder.terminate({
                "kind": "branch",
                "condition": _lower_expression(
                    arm.guard, builder.declared_functions, builder.enum_names
                ),
                "then": guarded_body,
                "else": unmatched,
            })
            builder.enter(guarded_body)
        _lower_statements(arm.body, builder, loop=loop)
        if builder.current_terminator() is None:
            if merge is None:
                merge = builder.new_block("match_merge")
            builder.jump_to(merge)
        builder.enter(unmatched)

    builder.terminate({
        "kind": "trap",
        "code": "RT-MATCH-001",
        "message": "match expression selected no arm",
    })
    if merge is not None:
        builder.enter(merge)


def _lower_pattern(pattern: Any) -> dict[str, Any]:
    if isinstance(pattern, IdentifierPatternNode):
        return {"kind": "binding", "name": pattern.name}
    if isinstance(pattern, (WildcardPatternNode, DefaultPatternNode)):
        return {"kind": "wildcard"}
    if isinstance(pattern, LiteralPatternNode):
        literal = pattern.value
        kind = {
            IntegerLiteralNode: "int",
            FloatLiteralNode: "float",
            BooleanLiteralNode: "bool",
            StringLiteralNode: "string",
            NullLiteralNode: "null",
        }[type(literal)]
        return {"kind": "literal", "value_kind": kind, "value": getattr(literal, "value", None)}
    if isinstance(pattern, RangePatternNode):
        return {
            "kind": "range",
            "lower": pattern.lower.value,
            "upper": pattern.upper.value,
            "lower_inclusive": pattern.lower_inclusive,
            "upper_inclusive": pattern.upper_inclusive,
        }
    if isinstance(pattern, EnumValuePatternNode):
        return {"kind": "enum", "enum_name": pattern.enum_name, "variant_name": pattern.value_name}
    if isinstance(pattern, QualifiedPatternNode):
        return {"kind": "enum", "enum_name": pattern.namespace, "variant_name": pattern.identifier}
    if isinstance(pattern, OptionalPatternNode):
        if pattern.kind == "None":
            return {"kind": "optional_none"}
        nested = {"kind": "binding", "name": pattern.binding} if pattern.binding else {"kind": "wildcard"}
        return {"kind": "optional_some", "pattern": nested}
    if isinstance(pattern, OptionalValuePatternNode):
        if pattern.kind == "None":
            return {"kind": "optional_none"}
        return {"kind": "optional_some", "pattern": _lower_pattern(pattern.pattern)}
    if isinstance(pattern, StructBindingPatternNode):
        return {"kind": "binding", "name": pattern.binding}
    if isinstance(pattern, StructPatternNode):
        return {
            "kind": "struct",
            "type_name": pattern.type_name,
            "fields": {
                field.field_name: _lower_pattern(field.pattern)
                for field in pattern.fields
            },
        }
    if isinstance(pattern, OrPatternNode):
        return {"kind": "or", "alternatives": [_lower_pattern(item) for item in pattern.alternatives]}
    raise LoweringError("IR-LOWER-010", f"unsupported pattern: {type(pattern).__name__}")


def _lower_if(statement: IfStatementNode, builder: _BlockBuilder, *, loop: _LoopTargets | None) -> None:
    declared_functions = builder.declared_functions
    enum_names = builder.enum_names
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
            "condition": _lower_expression(condition, declared_functions, enum_names),
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
    enum_names = builder.enum_names
    cond_block = builder.new_block("while_cond")
    body_block = builder.new_block("while_body")
    after_block = builder.new_block("while_after")
    loop_id = f"{builder.trace_scope}.while"
    trace_counter = f"__trace_iteration_{builder.counter}__"
    builder.emit({"op": "assign", "target": trace_counter, "expr": {"op": "const", "kind": "int", "value": 0}})
    builder.jump_to(cond_block)
    builder.enter(cond_block)
    builder.terminate({
        "kind": "branch",
        "condition": _lower_expression(statement.condition, declared_functions, enum_names),
        "then": body_block,
        "else": after_block,
    })
    builder.enter(body_block)
    builder.emit({"op": "trace_loop_start", "loop_id": loop_id, "counter": trace_counter})
    _lower_statements(
        statement.body,
        builder,
        loop=_LoopTargets(cond_block, after_block, loop_id),
    )
    if builder.current_terminator() is None:
        builder.emit({"op": "trace_loop_end", "loop_id": loop_id, "break_triggered": False, "continue_triggered": False})
        builder.jump_to(cond_block)
    builder.enter(after_block)


def _lower_loop(statement: LoopStatementNode, builder: _BlockBuilder) -> None:
    body_block = builder.new_block("loop_body")
    after_block = builder.new_block("loop_after")
    loop_id = f"{builder.trace_scope}.loop"
    trace_counter = f"__trace_iteration_{builder.counter}__"
    builder.emit({"op": "assign", "target": trace_counter, "expr": {"op": "const", "kind": "int", "value": 0}})
    builder.jump_to(body_block)
    builder.enter(body_block)
    builder.emit({"op": "trace_loop_start", "loop_id": loop_id, "counter": trace_counter})
    previous_scope = builder.trace_scope
    builder.trace_scope = loop_id
    try:
        _lower_statements(
            statement.body,
            builder,
            loop=_LoopTargets(body_block, after_block, loop_id),
        )
    finally:
        builder.trace_scope = previous_scope
    if builder.current_terminator() is None:
        builder.emit({"op": "trace_loop_end", "loop_id": loop_id, "break_triggered": False, "continue_triggered": False})
        builder.jump_to(body_block)
    builder.enter(after_block)


def _lower_for(statement: ForStatementNode, builder: _BlockBuilder) -> None:
    declared_functions = builder.declared_functions
    enum_names = builder.enum_names
    values_local = f"__for_values_{builder.counter + 1}__"
    index_local = f"__for_index_{builder.counter + 1}__"
    builder.emit({"op": "assign", "target": values_local, "expr": _lower_expression(statement.iterable, declared_functions, enum_names)})
    builder.emit({"op": "assign", "target": index_local, "expr": {"op": "const", "kind": "int", "value": 0}})

    cond_block = builder.new_block("for_cond")
    body_block = builder.new_block("for_body")
    increment_block = builder.new_block("for_increment")
    after_block = builder.new_block("for_after")
    loop_id = f"{builder.trace_scope}.for.{statement.iterator}"
    trace_counter = f"__trace_iteration_{builder.counter}__"
    builder.emit({"op": "assign", "target": trace_counter, "expr": {"op": "const", "kind": "int", "value": 0}})

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
    builder.emit({"op": "trace_loop_start", "loop_id": loop_id, "counter": trace_counter})
    previous_scope = builder.trace_scope
    builder.trace_scope = loop_id
    try:
        _lower_statements(
            statement.body,
            builder,
            loop=_LoopTargets(increment_block, after_block, loop_id),
        )
    finally:
        builder.trace_scope = previous_scope
    if builder.current_terminator() is None:
        builder.emit({"op": "trace_loop_end", "loop_id": loop_id, "break_triggered": False, "continue_triggered": False})
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


def _lower_expression(
    value: Any,
    declared_functions: dict[str, str],
    enum_names: set[str] | frozenset[str] = frozenset(),
) -> dict[str, Any]:
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
    if isinstance(value, NoneLiteralNode):
        return spanned({"op": "optional_none"})
    if isinstance(value, NullLiteralNode):
        return spanned({"op": "const", "kind": "null", "value": None})
    if isinstance(value, SomeExpressionNode):
        return spanned({
            "op": "optional_some",
            "value": _lower_expression(value.value, declared_functions, enum_names),
        })
    if isinstance(value, IdentifierNode):
        return spanned({"op": "local", "name": value.name})
    if isinstance(value, ArrayLiteralNode):
        return spanned({"op": "array", "elements": [_lower_expression(item, declared_functions, enum_names) for item in value.elements]})
    if isinstance(value, StructLiteralNode):
        return spanned({
            "op": "struct",
            "type_name": value.type_name,
            "fields": {field.name: _lower_expression(field.expression, declared_functions, enum_names) for field in value.fields},
        })
    if isinstance(value, ParenthesizedExpressionNode):
        return _lower_expression(value.expression, declared_functions, enum_names)
    if isinstance(value, UnaryExpressionNode):
        return spanned({
            "op": "unary",
            "operator": value.operator.value,
            "operand": _lower_expression(value.operand, declared_functions, enum_names),
        })
    if isinstance(value, BinaryExpressionNode):
        return spanned({
            "op": "binary",
            "operator": value.operator.value,
            "left": _lower_expression(value.left, declared_functions, enum_names),
            "right": _lower_expression(value.right, declared_functions, enum_names),
        })
    if isinstance(value, ComparisonExpressionNode):
        return spanned({
            "op": "comparison",
            "operator": value.operator.value,
            "left": _lower_expression(value.left, declared_functions, enum_names),
            "right": _lower_expression(value.right, declared_functions, enum_names),
        })
    if isinstance(value, LogicalExpressionNode):
        return spanned({
            "op": "logical",
            "operator": value.operator.value,
            "left": _lower_expression(value.left, declared_functions, enum_names),
            "right": _lower_expression(value.right, declared_functions, enum_names),
        })
    if isinstance(value, IndexAccessNode):
        return spanned({
            "op": "index",
            "collection": _lower_expression(value.collection, declared_functions, enum_names),
            "index": _lower_expression(value.index, declared_functions, enum_names),
        })
    if isinstance(value, MemberAccessNode):
        if isinstance(value.object, IdentifierNode) and value.object.name in enum_names:
            return spanned({
                "op": "enum_value",
                "enum_name": value.object.name,
                "variant_name": value.member,
            })
        return spanned({
            "op": "member",
            "object": _lower_expression(value.object, declared_functions, enum_names),
            "member": value.member,
        })
    if isinstance(value, RuntimeCallExpressionNode):
        function_id = {
            RuntimeCallKind.SEARCH: "runtime.search",
            RuntimeCallKind.SIMULATION: "runtime.simulate",
            RuntimeCallKind.PREDICTION: "runtime.predict",
            RuntimeCallKind.PLANNING: "runtime.plan",
        }.get(value.kind)
        if function_id is None:
            raise LoweringError(
                "IR-LOWER-006", f"unsupported Runtime call: {value.method}"
            )
        return spanned({
            "op": "call_reasoning",
            "function_id": function_id,
            "arguments": [
                _lower_expression(argument, declared_functions, enum_names)
                for argument in value.arguments
            ],
        })
    if isinstance(value, CallExpressionNode):
        return spanned(_lower_call(value, declared_functions, enum_names))
    raise LoweringError("IR-LOWER-006", f"unsupported expression: {type(value).__name__}")


def _lower_call(
    value: CallExpressionNode,
    declared_functions: dict[str, str],
    enum_names: set[str] | frozenset[str],
) -> dict[str, Any]:
    if (
        isinstance(value.callee, MemberAccessNode)
        and isinstance(value.callee.object, IdentifierNode)
        and value.callee.object.name == "ruo"
    ):
        return {
            "op": "call_ruo",
            "function_id": f"ruo.{value.callee.member}",
            "arguments": [_lower_expression(argument, declared_functions, enum_names) for argument in value.arguments],
        }
    vision_function = vision_call_name(value)
    if vision_function is not None:
        return {
            "op": "call_vision",
            "function_id": vision_function,
            "arguments": [_lower_expression(argument, declared_functions, enum_names) for argument in value.arguments],
        }
    tensor_function = tensor_call_name(value)
    if tensor_function is not None:
        return {
            "op": "call_tensor",
            "function_id": tensor_function,
            "arguments": [_lower_expression(argument, declared_functions, enum_names) for argument in value.arguments],
        }
    optimizer_function = optimizer_call_name(value)
    if optimizer_function is not None:
        return {
            "op": "call_optimizer",
            "function_id": optimizer_function,
            "arguments": [_lower_expression(argument, declared_functions, enum_names) for argument in value.arguments],
        }
    relation_function = relation_call_name(value)
    if relation_function is not None:
        return {
            "op": "call_relation",
            "function_id": relation_function,
            "arguments": [_lower_expression(argument, declared_functions, enum_names) for argument in value.arguments],
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
            "collection": _lower_expression(value.arguments[0], declared_functions, enum_names),
            "item": _lower_expression(value.arguments[1], declared_functions, enum_names),
        }
    if (
        isinstance(value.callee, MemberAccessNode)
        and isinstance(value.callee.object, IdentifierNode)
        and value.callee.object.name == "array"
        and value.callee.member == "concat"
    ):
        if len(value.arguments) != 2:
            raise LoweringError("IR-LOWER-007", "array.concat expects two arguments")
        return {
            "op": "call_array_concat",
            "left": _lower_expression(value.arguments[0], declared_functions, enum_names),
            "right": _lower_expression(value.arguments[1], declared_functions, enum_names),
        }
    if (
        isinstance(value.callee, MemberAccessNode)
        and isinstance(value.callee.object, IdentifierNode)
        and value.callee.object.name == "string"
    ):
        func_name = value.callee.member
        if func_name not in {"concat", "join", "length", "from_int", "from_float", "slice"}:
            raise LoweringError("IR-LOWER-009", f"unknown string standard function: string.{func_name}")
        return {
            "op": "call_string",
            "function_id": func_name,
            "arguments": [_lower_expression(arg, declared_functions, enum_names) for arg in value.arguments],
        }
    if isinstance(value.callee, IdentifierNode) and value.callee.name == "assert":
        if len(value.arguments) != 1:
            raise LoweringError("IR-LOWER-010", "assert expects 1 argument")
        return {
            "op": "call_assert",
            "condition": _lower_expression(value.arguments[0], declared_functions, enum_names),
        }
    if isinstance(value.callee, IdentifierNode) and value.callee.name == "assert_eq":
        if len(value.arguments) != 2:
            raise LoweringError("IR-LOWER-010", "assert_eq expects 2 arguments")
        return {
            "op": "call_assert_eq",
            "left": _lower_expression(value.arguments[0], declared_functions, enum_names),
            "right": _lower_expression(value.arguments[1], declared_functions, enum_names),
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
            "argument": _lower_expression(value.arguments[0], declared_functions, enum_names),
        }
    if isinstance(value.callee, IdentifierNode):
        return {
            "op": "call_function",
            "name": declared_functions.get(value.callee.name, value.callee.name),
            "arguments": [_lower_expression(argument, declared_functions, enum_names) for argument in value.arguments],
        }
    if isinstance(value.callee, QualifiedIdentifierNode):
        return {
            "op": "call_function",
            "name": value.callee.resolved_name
            or "::".join((*value.callee.path, value.callee.symbol)),
            "arguments": [_lower_expression(argument, declared_functions, enum_names) for argument in value.arguments],
        }
    raise LoweringError("IR-LOWER-009", "unsupported call target")
