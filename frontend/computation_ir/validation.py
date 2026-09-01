"""Structural validation for reason-computation-ir/0.1 documents.

Implements the Phase 2 "schema validation" item. Handwritten rather than
`jsonschema`-driven, consistent with the rest of this codebase's
validators (`toolchain.diagnostics.validate_diagnostics_document`,
`toolchain.artifacts.validate_artifact_directory`, ...), none of which
use the `jsonschema` package either. Checks structural well-formedness
(every terminator target resolves to a real block, every block is
reachable from the entry block, instruction/terminator/expression shapes
match the `op`-tagged vocabulary in `schema.py`) -- it does not check
Tensor shape/dtype compatibility or scope/name resolution, which the
language-surface validator (`frontend.language_surface.validation`)
already does before lowering ever runs.
"""

from __future__ import annotations

from typing import Any

from .schema import EXPRESSION_OPS, INSTRUCTION_OPS, PATTERN_KINDS, SCHEMA, TERMINATOR_KINDS


def validate_program(document: dict[str, Any]) -> list[str]:
    """Returns a list of human-readable errors; empty means the document is well-formed."""
    errors: list[str] = []
    if document.get("schema") != SCHEMA:
        errors.append(f"unexpected schema: {document.get('schema')!r}, expected {SCHEMA!r}")
    functions = document.get("functions")
    if not isinstance(functions, list):
        errors.append("'functions' must be a list")
        return errors
    function_ids = {function.get("id") for function in functions if isinstance(function, dict)}
    for calculation_id in document.get("calculations", []):
        if calculation_id not in function_ids:
            errors.append(f"calculation {calculation_id!r} has no matching Function")
    for function in functions:
        errors.extend(_validate_function(function))
    return errors


def _validate_function(function: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    function_id = function.get("id", "<unknown>")
    blocks = function.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        return [f"{function_id}: 'blocks' must be a non-empty list"]
    block_ids = {block.get("id") for block in blocks}
    entry = function.get("entry_block")
    if entry not in block_ids:
        errors.append(f"{function_id}: entry_block {entry!r} is not a known block")

    for block in blocks:
        block_id = block.get("id", "<unknown>")
        for instruction in block.get("instructions", []):
            errors.extend(_validate_instruction(function_id, block_id, instruction))
        terminator = block.get("terminator")
        errors.extend(_validate_terminator(function_id, block_id, terminator, block_ids))

    if entry in block_ids:
        reachable = _reachable_blocks(entry, {block["id"]: block for block in blocks})
        unreachable = block_ids - reachable
        for block_id in sorted(unreachable):
            errors.append(f"{function_id}: block {block_id!r} is unreachable from entry_block")
    return errors


def _validate_instruction(function_id: str, block_id: str, instruction: Any) -> list[str]:
    if not isinstance(instruction, dict) or instruction.get("op") not in INSTRUCTION_OPS:
        return [f"{function_id}/{block_id}: invalid instruction: {instruction!r}"]
    where = f"{function_id}/{block_id}"
    errors: list[str] = []
    for key in ("expr", "collection", "index", "object"):
        if key in instruction:
            errors.extend(_validate_expression(where, instruction[key]))
    return errors


def _validate_terminator(function_id: str, block_id: str, terminator: Any, block_ids: set[str]) -> list[str]:
    if not isinstance(terminator, dict) or terminator.get("kind") not in TERMINATOR_KINDS:
        return [f"{function_id}/{block_id}: invalid terminator: {terminator!r}"]
    where = f"{function_id}/{block_id}"
    errors: list[str] = []
    kind = terminator["kind"]
    if kind == "jump" and terminator.get("target") not in block_ids:
        errors.append(f"{where}: jump target {terminator.get('target')!r} unknown")
    if kind == "branch":
        for edge in ("then", "else"):
            if terminator.get(edge) not in block_ids:
                errors.append(f"{where}: branch {edge} target {terminator.get(edge)!r} unknown")
        errors.extend(_validate_expression(where, terminator.get("condition")))
    if kind in ("result", "return"):
        errors.extend(_validate_expression(where, terminator.get("value")))
    if kind == "match":
        errors.extend(_validate_expression(where, terminator.get("subject")))
        arms = terminator.get("arms")
        if not isinstance(arms, list) or not arms:
            errors.append(f"{where}: match 'arms' must be a non-empty list")
        else:
            for index, arm in enumerate(arms):
                if not isinstance(arm, dict):
                    errors.append(f"{where}: match arm {index} is not an object")
                    continue
                errors.extend(_validate_pattern(where, arm.get("pattern")))
                if arm.get("guard") is not None:
                    errors.extend(_validate_expression(where, arm["guard"]))
                if arm.get("target") not in block_ids:
                    errors.append(f"{where}: match arm {index} target {arm.get('target')!r} unknown")
    return errors


def _validate_expression(where: str, node: Any) -> list[str]:
    if not isinstance(node, dict) or node.get("op") not in EXPRESSION_OPS:
        return [f"{where}: invalid expression node: {node!r}"]
    errors: list[str] = []
    for key in ("left", "right", "operand", "collection", "index", "object", "argument"):
        if key in node:
            errors.extend(_validate_expression(where, node[key]))
    if node["op"] == "optional_some" and "value" in node:
        errors.extend(_validate_expression(where, node["value"]))
    for key in ("elements", "arguments"):
        if key in node:
            for item in node[key]:
                errors.extend(_validate_expression(where, item))
    if "fields" in node:
        for value in node["fields"].values():
            errors.extend(_validate_expression(where, value))
    return errors


def _validate_pattern(where: str, pattern: Any) -> list[str]:
    if not isinstance(pattern, dict) or pattern.get("kind") not in PATTERN_KINDS:
        return [f"{where}: invalid pattern node: {pattern!r}"]
    kind = pattern["kind"]
    errors: list[str] = []
    if kind == "optional_some":
        errors.extend(_validate_pattern(where, pattern.get("pattern")))
    if kind == "struct":
        fields = pattern.get("fields")
        if not isinstance(fields, dict):
            errors.append(f"{where}: struct pattern 'fields' must be an object")
        else:
            for field_pattern in fields.values():
                errors.extend(_validate_pattern(where, field_pattern))
    if kind == "or":
        alternatives = pattern.get("alternatives")
        if not isinstance(alternatives, list) or not alternatives:
            errors.append(f"{where}: or-pattern 'alternatives' must be a non-empty list")
        else:
            for alternative in alternatives:
                errors.extend(_validate_pattern(where, alternative))
    return errors


def _reachable_blocks(entry: str, blocks_by_id: dict[str, dict[str, Any]]) -> set[str]:
    seen: set[str] = set()
    stack = [entry]
    while stack:
        block_id = stack.pop()
        if block_id in seen or block_id not in blocks_by_id:
            continue
        seen.add(block_id)
        terminator = blocks_by_id[block_id].get("terminator") or {}
        if terminator.get("kind") == "jump":
            stack.append(terminator.get("target"))
        elif terminator.get("kind") == "branch":
            stack.append(terminator.get("then"))
            stack.append(terminator.get("else"))
        elif terminator.get("kind") == "match":
            for arm in terminator.get("arms") or []:
                if isinstance(arm, dict):
                    stack.append(arm.get("target"))
    return seen
