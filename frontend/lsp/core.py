"""In-process ReasonScript LSP Phase 1 services."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from frontend.language_surface import SurfaceSyntaxError, parse

from .model import (
    SCHEMA,
    CodeAction,
    CompletionItem,
    Diagnostic,
    DiagnosticSeverity,
    DocumentState,
    DocumentSymbol,
    FormattingOptions,
    Hover,
    Location,
    ParameterInformation,
    Position,
    Range,
    SemanticTokens,
    SemanticTokensLegend,
    SignatureHelp,
    SignatureInformation,
    Symbol,
    SymbolKind,
    TextEdit,
    WorkspaceEdit,
    point_range,
    position,
    range_for,
)

SEMANTIC_TOKEN_TYPES: tuple[str, ...] = (
    "keyword",
    "type",
    "class",
    "interface",
    "function",
    "method",
    "variable",
    "parameter",
    "property",
    "comment",
    "string",
    "number",
    "operator",
)

SEMANTIC_TOKEN_MODIFIERS: tuple[str, ...] = (
    "declaration",
    "definition",
    "readonly",
    "static",
    "defaultLibrary",
)

SEMANTIC_TOKENS_LEGEND = SemanticTokensLegend(SEMANTIC_TOKEN_TYPES, SEMANTIC_TOKEN_MODIFIERS)

KEYWORD_METADATA: dict[str, tuple[str, str]] = {
    "model": ("model <Name> { ... }", "Defines a reasoning model comprising state, constraints, transitions, and logic (preferred top-level construct)."),
    "module": ("module <Name> { ... }", "Defines a modular namespace for declarations and functions (backward-compatible top-level construct)."),
    "pub": ("pub <decl>", "Declares public visibility for a construct or member."),
    "fn": ("fn <name>(<params>) -> <Type> { ... }", "Declares a function or method."),
    "struct": ("struct <Name> { <fields> }", "Declares a composite structured type."),
    "enum": ("enum <Name> { <variants> }", "Declares an enumerated algebraic type."),
    "calculation": ("calculation <Name> { ... }", "Defines a deterministic calculation block."),
    "goal": ("goal <Name> { ... }", "Defines a reachability or optimization goal."),
    "state": ("state <Name> { ... }", "Declares state variables within a model."),
    "constraint": ("constraint <Name> { ... }", "Defines invariant constraints that must hold over states."),
    "transition": ("transition <Name>(<params>) { ... }", "Defines an action transitioning states."),
    "relation": ("relation <Name>(<params>) { ... }", "Defines relational predicates between entities."),
    "package": ("package <name>", "Declares the package namespace for the current file."),
    "import": ("import <path>", "Imports declarations from another module or package."),
    "export": ("export <symbol>", "Exports a symbol for use outside the package."),
    "const": ("const <name>: <type> = <val>", "Declares an immutable constant."),
    "let": ("let <name> = <val>", "Binds a local variable in scope."),
    "reason_graph": ("reason_graph <Name> { ... }", "Declares a graph-based reasoning pipeline."),
    "execution_plan": ("execution_plan <Name> { ... }", "Defines a sequence of scheduled actions."),
    "if": ("if <cond> { ... }", "Conditional execution block."),
    "elif": ("elif <cond> { ... }", "Alternative conditional branch."),
    "else": ("else { ... }", "Default conditional branch."),
    "match": ("match <expr> { ... }", "Pattern-matching construct."),
    "when": ("when <cond>", "Guard condition clause in pattern matching or transitions."),
    "for": ("for <item> in <iter> { ... }", "Iteration loop over a collection."),
    "while": ("while <cond> { ... }", "Conditional loop."),
    "loop": ("loop { ... }", "Unconditional infinite loop."),
    "break": ("break", "Breaks out of the current loop."),
    "continue": ("continue", "Skips to the next iteration of the loop."),
    "return": ("return <expr>", "Returns a value from the enclosing function."),
    "input": ("input <prompt>", "Reads input from standard environment."),
    "print": ("print(<expr>)", "Prints formatted output to standard output."),
    "search": ("search <goal>", "Initiates search for a satisfying path to a goal."),
    "simulate": ("simulate <model>", "Executes simulation of system transitions."),
    "predict": ("predict <state>", "Forecasts future trajectory from state."),
    "plan": ("plan <goal>", "Generates an execution plan for a goal."),
    "true": ("true", "Boolean true literal."),
    "false": ("false", "Boolean false literal."),
    "some": ("some(<val>)", "Optional value wrapper containing a value."),
    "none": ("none", "Optional empty value."),
}

API_METADATA: dict[str, tuple[str, str]] = {
    "print": ("fn print(value: any) -> void", "Prints formatted output to standard output."),
    "assert": ("fn assert(condition: bool, message: string = \"\") -> void", "Asserts that condition is true, raising an error otherwise."),
    "len": ("fn len(collection: any) -> int", "Returns the length of a collection."),
    "range": ("fn range(start: int, end: int, step: int = 1) -> list[int]", "Returns a range sequence."),
    "runtime.search": ("fn search(goal: Goal) -> ExecutionPlan", "Executes guided state-space search to discover a valid path satisfying the goal."),
    "runtime.plan": ("fn plan(goal: Goal, planner: Planner) -> PlanResult", "Synthesizes an execution plan for the target goal using the specified planner algorithm."),
    "runtime.predict": ("fn predict(state: State, horizon: int) -> SimulationTrace", "Rolls forward state transitions up to horizon steps to predict future trajectory."),
    "runtime.simulate": ("fn simulate(model: Model, steps: int) -> SimulationTrace", "Executes simulation of the model dynamics for the given number of steps."),
    "vision.infer": ("fn infer(image: Image) -> VisionObservation", "Runs perception model inference over visual sensor input."),
    "vision.build_ruo": ("fn build_ruo(obs: VisionObservation) -> RUO", "Constructs Reasoning Unit Objects (RUO) from visual observations."),
}

KEYWORD_COMPLETIONS = (
    # Top-level constructs — model preferred (v0.6-C), module compatible (v0.6-B)
    "model",
    "module",
    # Declarations
    "pub",
    "fn",
    "struct",
    "enum",
    "calculation",
    "goal",
    "state",
    "constraint",
    "transition",
    "relation",
    # Module system
    "package",
    "import",
    "export",
    "const",
    "let",
    "reason_graph",
    "execution_plan",
    # Control flow
    "if",
    "elif",
    "else",
    "match",
    "when",
    "for",
    "while",
    "loop",
    "break",
    "continue",
    "return",
    # Runtime operations
    "input",
    "print",
    "search",
    "simulate",
    "predict",
    "plan",
    # Literal keywords
    "true",
    "false",
    "some",
    "none",
    # Legacy
    "requires",
    "reach",
    # world / system / component are reserved — must NOT appear here (v0.6-D §6.3)
)
RUNTIME_APIS = ("runtime.search", "runtime.plan", "runtime.predict", "runtime.simulate")
VISION_APIS = ("vision.infer", "vision.build_ruo")
VISION_TYPES = ("VisionModel", "VisionObservation", "VisionBuildResult")
WORLD_TYPES = (
    "World",
    "Scene",
    "Entity",
    "Object",
    "Geometry",
    "Relation",
    "Event",
    "Snapshot",
    "SceneTemplate",
    "SimulationTrace",
)
PLANNING_TYPES = ("Goal", "Planner", "Plan", "PlanStep", "PlanResult")
AGENT_TYPES = ("Agent", "Task", "Decision", "Action", "Tool", "AgentResult")
REASONING_TYPES = ("Goal", "State", "Constraint", "ReasonGraph", "ExecutionPlan")

_BUILTIN_NAME_ORDER: tuple[str, ...] = tuple(
    dict.fromkeys((
        *RUNTIME_APIS,
        *VISION_APIS,
        *VISION_TYPES,
        *WORLD_TYPES,
        *PLANNING_TYPES,
        *AGENT_TYPES,
        *REASONING_TYPES,
    ))
)

BUILTIN_SYMBOLS = tuple(
    Symbol(
        name=name,
        kind=(
            "RuntimeAPI"
            if name.startswith("runtime.") or name.startswith("vision.")
            else "PlanningType"
            if name in PLANNING_TYPES
            else "AgentType"
            if name in AGENT_TYPES
            else "ReasoningType"
            if name in REASONING_TYPES
            else "WorldType"
        ),
        module=(
            "vision"
            if name.startswith("vision.")
            else "runtime"
            if name.startswith("runtime.")
            else "planning"
            if name in PLANNING_TYPES
            else "agent"
            if name in AGENT_TYPES
            else "reasoning"
            if name in REASONING_TYPES
            else "world"
        ),
        visibility="Public",
        location=Location("builtin://reasonscript-lsp", point_range(0, 0)),
        detail="ReasonScript built-in symbol",
    )
    for name in _BUILTIN_NAME_ORDER
)


DECLARATION_PATTERNS: tuple[tuple[str, str], ...] = (
    # Top-level constructs: Model (preferred) then Module (compatible) — v0.6-B/C/D
    # world / system / component are reserved and must NOT be scanned (v0.6-D §7.3)
    ("Model", r"(?:(?:pub|export)\s+)?model\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{"),
    ("Module", r"(?:(?:pub|export)\s+)?module\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{"),
    # Inner declarations
    ("Function", r"(?:(?:pub|export)\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    ("Calculation", r"(?:(?:pub|export)\s+)?calculation\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{"),
    ("Struct", r"(?:(?:pub|export)\s+)?struct\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{"),
    ("Enum", r"(?:(?:pub|export)\s+)?enum\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{"),
    ("Const", r"(?:(?:pub|export)\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ("Goal", r"goal\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ("State", r"state\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ("Constraint", r"constraint\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ("Transition", r"(?:(?:pub|export)\s+)?transition\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    ("Relation", r"(?:(?:pub|export)\s+)?relation\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    ("ReasonGraph", r"reason_graph\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{"),
    ("ExecutionPlan", r"execution_plan\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{"),
)

SYMBOL_KIND_MAP: dict[str, int] = {
    "Model": int(SymbolKind.CLASS),
    "Module": int(SymbolKind.MODULE),
    "Function": int(SymbolKind.FUNCTION),
    "Calculation": int(SymbolKind.FUNCTION),
    "Struct": int(SymbolKind.STRUCT),
    "Enum": int(SymbolKind.ENUM),
    "Const": int(SymbolKind.CONSTANT),
    "Goal": int(SymbolKind.EVENT),
    "State": int(SymbolKind.FIELD),
    "Constraint": int(SymbolKind.EVENT),
    "Transition": int(SymbolKind.METHOD),
    "Relation": int(SymbolKind.INTERFACE),
    "ReasonGraph": int(SymbolKind.CLASS),
    "ExecutionPlan": int(SymbolKind.CLASS),
    "Package": int(SymbolKind.PACKAGE),
    # Lowercase aliases
    "model": int(SymbolKind.CLASS),
    "module": int(SymbolKind.MODULE),
    "function": int(SymbolKind.FUNCTION),
    "calculation": int(SymbolKind.FUNCTION),
    "struct": int(SymbolKind.STRUCT),
    "enum": int(SymbolKind.ENUM),
    "const": int(SymbolKind.CONSTANT),
    "goal": int(SymbolKind.EVENT),
    "state": int(SymbolKind.FIELD),
    "constraint": int(SymbolKind.EVENT),
    "transition": int(SymbolKind.METHOD),
    "relation": int(SymbolKind.INTERFACE),
    "package": int(SymbolKind.PACKAGE),
    "variable": int(SymbolKind.VARIABLE),
}


@dataclass(frozen=True)
class _Token:
    text: str
    range: Range


def _extract_doc_comments(text: str, decl_line: int) -> str:
    lines = text.splitlines()
    if decl_line <= 0 or decl_line > len(lines):
        return ""
    comments: list[str] = []
    idx = decl_line - 1
    while idx >= 0:
        raw = lines[idx].strip()
        if raw.startswith("///"):
            comments.append(raw[3:].strip())
        elif raw.startswith("//"):
            comments.append(raw[2:].strip())
        else:
            break
        idx -= 1
    comments.reverse()
    return "\n".join(comments)


def _resolve_local_symbol(text: str, cursor_line: int, token_text: str, uri: str) -> dict[str, Any] | None:
    lines = text.splitlines()
    if cursor_line < 0 or cursor_line >= len(lines):
        return None

    # Find the enclosing function or calculation
    func_start_line = -1
    func_name = "function"
    for l_idx in range(cursor_line, -1, -1):
        line = lines[l_idx].split("//", 1)[0]
        fn_match = re.search(r"(?:(?:pub|export)\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)", line)
        calc_match = re.search(r"(?:(?:pub|export)\s+)?calculation\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", line)
        if fn_match:
            func_start_line = l_idx
            func_name = fn_match.group(1)
            params_str = fn_match.group(2)
            for p_match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\b(?:\s*:\s*([A-Za-z_][A-Za-z0-9_]*))?", params_str):
                p_name = p_match.group(1)
                if p_name == token_text:
                    p_type = p_match.group(2) or "any"
                    p_col = fn_match.start(2) + p_match.start(1)
                    loc = Location(uri, range_for(l_idx, p_col, p_name))
                    return {
                        "name": p_name,
                        "kind": "parameter",
                        "type": p_type,
                        "container": func_name,
                        "location": loc,
                        "contents": f"```reasonscript\n(parameter) {p_name}: {p_type}\n```\n---\n*Parameter in `{func_name}`*",
                    }
            break
        elif calc_match:
            func_start_line = l_idx
            func_name = calc_match.group(1)
            break

    start_search = max(func_start_line, 0)
    for l_idx in range(start_search, cursor_line + 1):
        line = lines[l_idx].split("//", 1)[0]
        var_match = re.search(rf"\b(?:let|const)\s+({re.escape(token_text)})\b(?:\s*:\s*([A-Za-z_][A-Za-z0-9_]*))?", line)
        if var_match:
            v_name = var_match.group(1)
            v_type = var_match.group(2) or "inferred"
            v_col = var_match.start(1)
            loc = Location(uri, range_for(l_idx, v_col, v_name))
            return {
                "name": v_name,
                "kind": "variable",
                "type": v_type,
                "container": func_name,
                "location": loc,
                "contents": f"```reasonscript\n(variable) {v_name}: {v_type}\n```\n---\n*Local variable in `{func_name}`*",
            }

    return None


def _extract_document_symbols(text: str) -> tuple[DocumentSymbol, ...]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return ()

    line_starts: list[int] = [0]
    for line in lines[:-1]:
        line_starts.append(line_starts[-1] + len(line))

    def offset_to_pos(offset: int) -> Position:
        import bisect
        l_idx = bisect.bisect_right(line_starts, offset) - 1
        c_idx = offset - line_starts[l_idx]
        return Position(l_idx, c_idx)

    # Find brace pairs in text
    open_stack: list[int] = []
    brace_pairs: dict[int, int] = {}
    in_comment = False
    for idx, ch in enumerate(text):
        if ch == "\n":
            in_comment = False
        elif text[idx:idx + 2] == "//":
            in_comment = True
        if in_comment:
            continue
        if ch == "{":
            open_stack.append(idx)
        elif ch == "}":
            if open_stack:
                s_idx = open_stack.pop()
                brace_pairs[s_idx] = idx

    for s_idx in open_stack:
        brace_pairs[s_idx] = len(text) - 1

    # 1. Collect all raw matches
    raw_matches: list[dict[str, Any]] = []
    for kind_name, pattern in DECLARATION_PATTERNS:
        for match in re.finditer(pattern, text):
            line_pos = offset_to_pos(match.start())
            raw_line = lines[line_pos.line]
            comment_idx = raw_line.find("//")
            if comment_idx != -1 and line_pos.character >= comment_idx:
                continue

            raw_matches.append({
                "kind_name": kind_name,
                "name": match.group(1),
                "start": match.start(),
                "selection_start": match.start(1),
                "selection_end": match.end(1),
            })

    # Sort matches by start position
    raw_matches.sort(key=lambda m: m["start"])

    # 2. Compute scope end for each match
    raw_symbols: list[dict[str, Any]] = []
    for i, m in enumerate(raw_matches):
        decl_start = m["start"]
        next_start = raw_matches[i + 1]["start"] if i + 1 < len(raw_matches) else len(text)

        # Look for '{' or ';' between decl_start and next_start
        brace_pos = text.find("{", decl_start)
        semi_pos = text.find(";", decl_start)

        scope_end: int
        if brace_pos != -1 and brace_pos < next_start and brace_pos in brace_pairs:
            scope_end = brace_pairs[brace_pos]
        elif semi_pos != -1 and (brace_pos == -1 or semi_pos < brace_pos) and semi_pos < next_start:
            scope_end = semi_pos
        else:
            nl_pos = text.find("\n", decl_start)
            candidates = [p for p in (semi_pos, nl_pos) if p != -1 and p <= next_start]
            scope_end = min(candidates) if candidates else next_start

        kind_int = SYMBOL_KIND_MAP.get(m["kind_name"], int(SymbolKind.VARIABLE))
        raw_decl = text[decl_start:min(decl_start + 60, scope_end)].split("\n", 1)[0].rstrip("{").strip()

        raw_symbols.append({
            "name": m["name"],
            "detail": raw_decl if raw_decl else f"{m['kind_name']} {m['name']}",
            "kind": kind_int,
            "start": decl_start,
            "end": scope_end,
            "selection_start": m["selection_start"],
            "selection_end": m["selection_end"],
            "children": [],
        })

    # Sort raw symbols: earliest start first; wider scope first
    raw_symbols.sort(key=lambda s: (s["start"], -s["end"]))

    # Build hierarchy: symbol B is a child of A if A strictly encloses B
    root_symbols: list[dict[str, Any]] = []

    def try_insert(parent: dict[str, Any], sym: dict[str, Any]) -> bool:
        # parent must enclose sym
        if not (parent["start"] <= sym["start"] and sym["end"] <= parent["end"]):
            return False
        # Identical ranges cannot be parent-child
        if parent["start"] == sym["start"] and parent["end"] == sym["end"]:
            return False

        for child in parent["children"]:
            if try_insert(child, sym):
                return True

        parent["children"].append(sym)
        return True

    for sym in raw_symbols:
        placed = False
        for root in root_symbols:
            if try_insert(root, sym):
                placed = True
                break
        if not placed:
            root_symbols.append(sym)

    def convert(item: dict[str, Any]) -> DocumentSymbol:
        return DocumentSymbol(
            name=item["name"],
            detail=item["detail"],
            kind=item["kind"],
            range=Range(offset_to_pos(item["start"]), offset_to_pos(item["end"])),
            selection_range=Range(offset_to_pos(item["selection_start"]), offset_to_pos(item["selection_end"])),
            children=tuple(convert(c) for c in item["children"]),
        )

    return tuple(convert(r) for r in root_symbols)


def _extract_semantic_tokens(text: str) -> tuple[int, ...]:
    lines = text.splitlines()
    if not lines:
        return ()

    type_idx = {name: idx for idx, name in enumerate(SEMANTIC_TOKEN_TYPES)}
    mod_bit = {name: 1 << idx for idx, name in enumerate(SEMANTIC_TOKEN_MODIFIERS)}

    raw_tokens: list[tuple[int, int, int, int, int]] = []

    keyword_set = set(KEYWORD_COMPLETIONS)
    all_types = set((*VISION_TYPES, *WORLD_TYPES, *PLANNING_TYPES, *AGENT_TYPES, *REASONING_TYPES))
    builtin_apis = set((*RUNTIME_APIS, *VISION_APIS))

    for line_idx, line in enumerate(lines):
        # 1. Comments
        comment_pos = line.find("//")
        code_part = line if comment_pos == -1 else line[:comment_pos]
        if comment_pos != -1:
            raw_tokens.append((line_idx, comment_pos, len(line) - comment_pos, type_idx["comment"], 0))

        # 2. String literals
        for m in re.finditer(r'"[^"\\]*(?:\\.[^"\\]*)*"', code_part):
            raw_tokens.append((line_idx, m.start(), len(m.group(0)), type_idx["string"], 0))

        # 3. Numeric literals
        for m in re.finditer(r"\b\d+\b", code_part):
            raw_tokens.append((line_idx, m.start(), len(m.group(0)), type_idx["number"], 0))

        # 4. Declarations (names)
        for decl_kind, pat in DECLARATION_PATTERNS:
            for m in re.finditer(pat, code_part):
                name = m.group(1)
                name_start = m.start(1)
                target_type = (
                    type_idx["class"]
                    if decl_kind in ("Model", "Module", "ReasonGraph", "ExecutionPlan")
                    else type_idx["function"]
                    if decl_kind in ("Function", "Calculation", "Transition")
                    else type_idx["interface"]
                    if decl_kind == "Relation"
                    else type_idx["type"]
                    if decl_kind in ("Struct", "Enum")
                    else type_idx["variable"]
                )
                mods = mod_bit["declaration"] | mod_bit["definition"]
                if decl_kind == "Const":
                    mods |= mod_bit["readonly"]
                raw_tokens.append((line_idx, name_start, len(name), target_type, mods))

        # 5. Builtin APIs (dotted)
        for api in builtin_apis:
            for m in re.finditer(rf"\b{re.escape(api)}\b", code_part):
                raw_tokens.append((line_idx, m.start(), len(api), type_idx["function"], mod_bit["defaultLibrary"]))

        # 6. Keywords & Types & Identifiers
        for m in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", code_part):
            word = m.group(0)
            w_start = m.start()
            if word in keyword_set:
                raw_tokens.append((line_idx, w_start, len(word), type_idx["keyword"], 0))
            elif word in all_types or word in ("int", "float", "bool", "string", "void", "any"):
                raw_tokens.append((line_idx, w_start, len(word), type_idx["type"], mod_bit["defaultLibrary"]))

    # Sort tokens: earliest line first; earliest col first; longer length first
    raw_tokens.sort(key=lambda t: (t[0], t[1], -t[2]))

    # Deduplicate overlapping tokens (keep first/highest priority)
    non_overlapping: list[tuple[int, int, int, int, int]] = []
    for tok in raw_tokens:
        if not non_overlapping:
            non_overlapping.append(tok)
            continue
        last = non_overlapping[-1]
        if tok[0] == last[0] and tok[1] < last[1] + last[2]:
            continue
        non_overlapping.append(tok)

    # Relative encoding
    encoded: list[int] = []
    prev_line = 0
    prev_col = 0
    for t_line, t_col, length, t_type, t_mods in non_overlapping:
        delta_line = t_line - prev_line
        delta_start = t_col if delta_line > 0 else t_col - prev_col
        encoded.extend([delta_line, delta_start, length, t_type, t_mods])
        prev_line = t_line
        prev_col = t_col

    return tuple(encoded)


def _format_reasonscript(text: str, options: FormattingOptions | None = None) -> str:
    lines = text.splitlines()
    if not lines:
        return ""

    indent_size = options.tab_size if options else 4
    indent_unit = " " * indent_size if (options is None or options.insert_spaces) else "\t"

    formatted_lines: list[str] = []
    current_indent = 0
    prev_blank = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not prev_blank and formatted_lines:
                formatted_lines.append("")
                prev_blank = True
            continue
        prev_blank = False

        # Adjust indent for closing braces
        closing_count = stripped.count("}") - stripped.count("{")
        if stripped.startswith("}"):
            current_indent = max(current_indent - 1, 0)

        # Normalize spaces around operators and delimiters outside strings
        comment_idx = stripped.find("//")
        code_str = stripped if comment_idx == -1 else stripped[:comment_idx]
        comment_str = "" if comment_idx == -1 else stripped[comment_idx:]

        # Normalise colon spacing: ' :' -> ':', ':x' -> ': x'
        norm_code = re.sub(r"\s*:\s*([A-Za-z_])", r": \1", code_str)
        # Normalise arrow: ' -> '
        norm_code = re.sub(r"\s*->\s*", " -> ", norm_code)
        # Normalise comma spacing: ',x' -> ', x'
        norm_code = re.sub(r",\s*", ", ", norm_code)
        # Normalise comparisons: '==', '!=', '<=', '>='
        norm_code = re.sub(r"\s*(==|!=|<=|>=)\s*", r" \1 ", norm_code)
        # Normalise assignment: ' = ' (excluding ==, !=, <=, >=)
        norm_code = re.sub(r"(?<![=!<>])\s*=\s*(?![=])", " = ", norm_code)
        # Normalise '<', '>' (not part of <=, >=, ->)
        norm_code = re.sub(r"(?<![-=<>!])\s*([<>])\s*(?![=])", r" \1 ", norm_code)
        # Normalise binary operators '+', '*', '/'
        norm_code = re.sub(r"(?<=[A-Za-z0-9_])\s*(\+|\*|\/)\s*(?=[A-Za-z0-9_])", r" \1 ", norm_code)
        # Normalise binary '-' (when preceded and followed by identifiers/digits)
        norm_code = re.sub(r"(?<=[A-Za-z0-9_])\s*-\s*(?=[A-Za-z0-9_])", " - ", norm_code)
        # Normalise opening brace preceded by non-space: 'int{' -> 'int {'
        norm_code = re.sub(r"(?<=\S)\{", " {", norm_code)

        # Blank line before top-level declarations if needed
        is_top_decl = any(norm_code.startswith(kw + " ") or norm_code.startswith("pub " + kw + " ") for kw in ("model", "module", "fn", "struct", "enum", "calculation", "goal", "state"))
        if is_top_decl and current_indent == 0 and formatted_lines and formatted_lines[-1] != "":
            formatted_lines.append("")

        indented = (indent_unit * current_indent) + norm_code.strip()
        if comment_str:
            if norm_code.strip():
                indented = f"{indented} {comment_str.strip()}"
            else:
                indented = (indent_unit * current_indent) + comment_str.strip()

        formatted_lines.append(indented)

        # Adjust indent for opening braces
        open_count = stripped.count("{") - stripped.count("}")
        if open_count > 0:
            current_indent += open_count
        elif closing_count > 0 and not stripped.startswith("}"):
            current_indent = max(current_indent - closing_count, 0)

    # Ensure single trailing newline
    return "\n".join(formatted_lines) + "\n"


def _extract_signature_help(text: str, line: int, character: int, server: ReasonScriptLanguageServer) -> SignatureHelp | None:
    lines = text.splitlines()
    if line < 0 or line >= len(lines):
        return None
    curr_line = lines[line]
    prefix = curr_line[:max(character, 0)]

    # Search backwards for unclosed '('
    open_paren = -1
    paren_depth = 0
    comma_count = 0
    for idx in range(len(prefix) - 1, -1, -1):
        ch = prefix[idx]
        if ch == ")":
            paren_depth += 1
        elif ch == "(":
            if paren_depth > 0:
                paren_depth -= 1
            else:
                open_paren = idx
                break
        elif ch == "," and paren_depth == 0:
            comma_count += 1

    if open_paren == -1:
        return None

    # Get function/callee name before open_paren
    callee_match = re.search(r"([A-Za-z_][A-Za-z0-9_.]*)\s*$", prefix[:open_paren])
    if not callee_match:
        return None
    callee_name = callee_match.group(1)

    # 1. Built-in API
    if callee_name in API_METADATA:
        sig_str, doc_str = API_METADATA[callee_name]
        param_match = re.search(r"\(([^)]*)\)", sig_str)
        params: list[ParameterInformation] = []
        if param_match and param_match.group(1).strip():
            for p in param_match.group(1).split(","):
                params.append(ParameterInformation(label=p.strip()))
        active_idx = min(comma_count, max(len(params) - 1, 0))
        sig_label = f"fn {callee_name}{sig_str[sig_str.find('('):]}" if sig_str.startswith("fn ") else f"{callee_name}{sig_str[sig_str.find('('):]}"
        sig_info = SignatureInformation(
            label=sig_label,
            documentation=doc_str,
            parameters=tuple(params),
            active_parameter=active_idx,
        )
        return SignatureHelp(signatures=(sig_info,), active_signature=0, active_parameter=active_idx)

    # 2. User-defined function
    simple_name = callee_name.split(".")[-1].split("::")[-1]
    for s_line in text.splitlines():
        fn_match = re.search(rf"(?:(?:pub|export)\s+)?fn\s+{re.escape(simple_name)}\s*\(([^)]*)\)(?:\s*->\s*([A-Za-z_][A-Za-z0-9_]*))?", s_line)
        if fn_match:
            raw_params = fn_match.group(1)
            ret_type = fn_match.group(2) or "void"
            params = [ParameterInformation(label=p.strip()) for p in raw_params.split(",") if p.strip()]
            active_idx = min(comma_count, max(len(params) - 1, 0))
            sig_label = f"fn {simple_name}({raw_params.strip()}) -> {ret_type}"
            sig_info = SignatureInformation(
                label=sig_label,
                documentation=f"User-defined function `{simple_name}`",
                parameters=tuple(params),
                active_parameter=active_idx,
            )
            return SignatureHelp(signatures=(sig_info,), active_signature=0, active_parameter=active_idx)

    return None


def _word_at(text: str, position_line: int, character: int) -> _Token | None:
    lines = text.splitlines()
    if position_line < 0 or position_line >= len(lines):
        return None
    line = lines[position_line]
    character = min(max(character, 0), len(line))
    pattern = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    for match in pattern.finditer(line):
        if match.start() <= character <= match.end():
            return _Token(match.group(0), range_for(position_line, match.start(), match.group(0)))
    return None


def _module_for_line(text: str, line_number: int) -> str:
    """Return the top-level scope name that contains the given line.

    Recognises both ``model`` (preferred, v0.6-B) and ``module`` (compatible).
    Short-term name kept for backwards compatibility; rename to
    ``_top_level_scope_for_line`` is recommended per IDE spec §8.2.
    """
    package = ""
    current = "main"
    for index, line in enumerate(text.splitlines()):
        if index > line_number:
            break
        package_match = re.match(r"\s*package\s+([A-Za-z_][A-Za-z0-9_.]*)", line)
        if package_match:
            package = package_match.group(1)
        # v0.6-B: both model (preferred) and module (compatible) define top-level scope
        top_level_match = re.match(
            r"\s*(?:(?:pub|export)\s+)?(?:model|module)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{",
            line,
        )
        if top_level_match:
            current = top_level_match.group(1)
    return f"{package}.{current}" if package else current


def _scan_symbols(uri: str, text: str) -> tuple[Symbol, ...]:
    symbols: list[Symbol] = []
    package = ""
    current_module = "main"
    for line_number, raw_line in enumerate(text.splitlines()):
        line = raw_line.split("//", 1)[0]
        package_match = re.match(r"\s*package\s+([A-Za-z_][A-Za-z0-9_.]*)", line)
        if package_match:
            package = package_match.group(1)
            continue
        # Check model (index 0) then module (index 1) for top-level scope tracking
        for top_idx in range(2):
            top_match = re.match(DECLARATION_PATTERNS[top_idx][1], line.strip())
            if top_match:
                current_module = top_match.group(1)
                break
        module = f"{package}.{current_module}" if package else current_module
        for kind, pattern in DECLARATION_PATTERNS:
            match = re.search(pattern, line)
            if match is None:
                continue
            name = match.group(1)
            start = match.start(1)
            private_kinds = {"Function", "Calculation", "Struct", "Enum", "Const", "Transition", "Relation"}
            visibility = "Public" if re.match(r"\s*(pub|export)\b", line) or kind not in private_kinds else "Private"
            detail = f"{kind} {name}" if kind in {"Model", "Module"} else f"{kind} {module}::{name}"
            symbols.append(
                Symbol(
                    name=name,
                    kind=kind,
                    module=module if kind not in {"Model", "Module"} else (f"{package}.{name}" if package else name),
                    visibility=visibility,
                    location=Location(uri, range_for(line_number, start, name)),
                    detail=detail,
                )
            )
            break
    return tuple(symbols)


class DiagnosticCode(str):
    """String wrapper supporting legacy diagnostic code comparison for backward compatibility."""

    def __eq__(self, other: object) -> bool:
        val = str(self)
        other_str = str(other) if isinstance(other, (str, DiagnosticCode)) else None
        if other_str is not None:
            if val == other_str:
                return True
            try:
                from toolchain.diagnostics import DEFAULT_REGISTRY

                if DEFAULT_REGISTRY.canonical_code(val) == DEFAULT_REGISTRY.canonical_code(other_str):
                    return True
            except Exception:
                pass
        if val in ("PAR-0001", "LEX-0001") and other == "SyntaxError":
            return True
        if val.startswith("NAM-") and other in ("UnknownModule", "UnknownSymbol", "VisibilityViolation"):
            return True
        if val.startswith("TYP-") and other == "TypeMismatch":
            return True
        return False


def _syntax_diagnostic(uri: str, message: str) -> Diagnostic:
    line = 0
    character = 0
    match = re.search(r"at\s+(\d+):(\d+)", message)
    if match:
        line = max(int(match.group(1)) - 1, 0)
        character = max(int(match.group(2)) - 1, 0)
    return Diagnostic(
        DiagnosticSeverity.ERROR,
        DiagnosticCode(_diagnostic_code(message)),
        message,
        Location(uri, point_range(line, character)),
    )


def _diagnostic_code(message: str) -> str:
    if "ModuleNotFound" in message or "import target does not exist" in message:
        return "UnknownModule"
    if "unknown" in message.lower() or "does not exist" in message:
        return "UnknownSymbol"
    if "private symbol" in message:
        return "VisibilityViolation"
    if "TYPE" in message or "type" in message.lower():
        return "TypeMismatch"
    return "SyntaxError"


class ReasonScriptLanguageServer:
    """Phase 1 language server core.

    The class intentionally exposes editor-neutral methods so tests and future
    transports can reuse the same analysis engine.
    """

    schema = SCHEMA

    def __init__(self) -> None:
        self.documents: dict[str, DocumentState] = {}
        self.symbols: dict[str, tuple[Symbol, ...]] = {}
        self.package_graph = None

    def open_document(self, uri: str, text: str, version: int = 1) -> DocumentState:
        return self._analyze(uri, text, version)

    def change_document(self, uri: str, text: str, version: int) -> DocumentState:
        return self._analyze(uri, text, version)

    def save_document(self, uri: str) -> DocumentState:
        if uri not in self.documents:
            return self._analyze(uri, "", 1)
        return self.documents[uri]

    def scan_workspace(self, root: str | Path) -> tuple[Symbol, ...]:
        root_path = Path(root)
        self.load_package_graph(root_path)
        for path in sorted(root_path.rglob("*.rsn")):
            uri = path.resolve().as_uri()
            self._analyze(uri, path.read_text(encoding="utf-8"), 1)
        return self.workspace_symbols()

    def load_package_graph(self, root: str | Path):
        try:
            from toolchain.workspace import PackageGraphService

            self.package_graph = PackageGraphService().discover(root).graph
        except Exception:
            self.package_graph = None
        return self.package_graph

    def diagnostics(self, uri: str) -> tuple[Diagnostic, ...]:
        doc = self.documents.get(uri)
        return doc.diagnostics if doc is not None else ()

    def completion(self, uri: str, line: int, character: int) -> tuple[CompletionItem, ...]:
        symbol_items = [
            CompletionItem(symbol.name, symbol.kind, symbol.detail, f"Defined in {symbol.module} ({symbol.visibility})")
            for symbol in self.workspace_symbols()
            if symbol.location.uri != "builtin://reasonscript-lsp"
        ]
        keyword_items = [
            CompletionItem(
                label,
                "Keyword",
                detail=KEYWORD_METADATA.get(label, ("", ""))[0],
                documentation=KEYWORD_METADATA.get(label, ("", ""))[1],
            )
            for label in KEYWORD_COMPLETIONS
        ]
        runtime_items = [
            CompletionItem(
                label,
                "RuntimeAPI",
                detail=API_METADATA.get(label, ("", ""))[0],
                documentation=API_METADATA.get(label, ("", ""))[1],
            )
            for label in RUNTIME_APIS
        ]
        vision_items = [
            CompletionItem(
                label,
                "VisionAPI",
                detail=API_METADATA.get(label, ("", ""))[0],
                documentation=API_METADATA.get(label, ("", ""))[1],
            )
            for label in VISION_APIS
        ]

        # Check line prefix for dot context (e.g., "runtime.", "vision.")
        doc = self.documents.get(uri)
        if doc and 0 <= line < len(doc.text.splitlines()):
            prefix = doc.text.splitlines()[line][:character]
            if prefix.endswith("runtime."):
                return tuple(runtime_items)
            if prefix.endswith("vision."):
                return tuple(vision_items)

        return tuple(
            [
                *keyword_items,
                *runtime_items,
                *vision_items,
                *(CompletionItem(label, "VisionType", detail=label, documentation=f"Vision runtime type {label}") for label in VISION_TYPES),
                *(CompletionItem(label, "WorldType", detail=label, documentation=f"World construct type {label}") for label in WORLD_TYPES),
                *(CompletionItem(label, "PlanningType", detail=label, documentation=f"Planning construct type {label}") for label in PLANNING_TYPES),
                *(CompletionItem(label, "AgentType", detail=label, documentation=f"Agent construct type {label}") for label in AGENT_TYPES),
                *(CompletionItem(label, "ReasoningType", detail=label, documentation=f"Reasoning model type {label}") for label in REASONING_TYPES),
                *symbol_items,
            ]
        )

    def hover(self, uri: str, line: int, character: int) -> Hover | None:
        document = self.documents.get(uri)
        if document is None:
            return None
        token = _word_at(document.text, line, character)
        if token is None:
            return None

        # 1. Check API metadata (supporting dotted calls like runtime.search, vision.infer)
        full_token_text = token.text
        hover_range = token.range
        doc_lines = document.text.splitlines()
        if 0 <= line < len(doc_lines):
            line_str = doc_lines[line]
            for api_name in API_METADATA:
                for m in re.finditer(rf"\b{re.escape(api_name)}\b", line_str):
                    if m.start() <= character <= m.end():
                        full_token_text = api_name
                        hover_range = range_for(line, m.start(), api_name)
                        break

        if full_token_text in API_METADATA:
            sig, doc = API_METADATA[full_token_text]
            api_kind = "VisionAPI" if full_token_text.startswith("vision.") else "RuntimeAPI"
            contents = "\n".join([
                api_kind,
                f"Name: {full_token_text}",
                f"Type: {api_kind}",
                f"Module: {full_token_text.split('.')[0]}",
                "",
                "```reasonscript",
                f"{full_token_text}: {sig}",
                "```",
                "---",
                doc,
            ])
            return Hover(contents, hover_range)

        # 2. Check local symbol (parameter / variable) before keywords
        local_info = _resolve_local_symbol(document.text, line, token.text, uri)
        if local_info is not None:
            return Hover(local_info["contents"], token.range)

        # 3. Check Keyword metadata
        if token.text in KEYWORD_METADATA:
            sig, doc = KEYWORD_METADATA[token.text]
            contents = "\n".join([
                "Keyword",
                f"Name: {token.text}",
                "Type: Keyword",
                "Module: language",
                "",
                "```reasonscript",
                sig,
                "```",
                "---",
                doc,
            ])
            return Hover(contents, token.range)

        # 4. Check resolved symbols
        symbol = self._resolve_token(uri, token.text, line, token.range.start.character)
        if symbol is None:
            return None

        # Extract declaration signature and doc comments if local
        sig = f"{symbol.kind} {symbol.name}"
        doc_comments = ""
        sym_doc = self.documents.get(symbol.location.uri)
        if sym_doc and symbol.location.range:
            s_line = symbol.location.range.start.line
            doc_lines = sym_doc.text.splitlines()
            if 0 <= s_line < len(doc_lines):
                raw_decl = doc_lines[s_line].strip()
                if raw_decl:
                    sig = raw_decl.rstrip("{").strip()
            doc_comments = _extract_doc_comments(sym_doc.text, s_line)

        contents_parts = [
            symbol.kind,
            f"Name: {symbol.name}",
            f"Type: {symbol.kind}",
            f"Module: {symbol.module}",
            "",
            "```reasonscript",
            sig,
            "```",
            "---",
            f"**Visibility**: `{symbol.visibility}`",
        ]
        if symbol.detail:
            contents_parts.append(f"*{symbol.detail}*")
        if doc_comments:
            contents_parts.append("")
            contents_parts.append(doc_comments)

        return Hover("\n".join(contents_parts), token.range)

    def definition(self, uri: str, line: int, character: int) -> Location | None:
        document = self.documents.get(uri)
        if document is None:
            return None
        token = _word_at(document.text, line, character)
        if token is None:
            return None

        # 1. Check local variable or parameter first (highest precedence)
        local_info = _resolve_local_symbol(document.text, line, token.text, uri)
        if local_info is not None:
            return local_info["location"]

        # 2. Check qualified or module/global symbol
        symbol = self._resolve_token(uri, token.text, line, token.range.start.character)
        return symbol.location if symbol is not None else None

    def document_symbols(self, uri: str) -> tuple[DocumentSymbol, ...]:
        document = self.documents.get(uri)
        if document is None:
            return ()
        return _extract_document_symbols(document.text)

    def code_actions(self, uri: str, range_obj: Range) -> tuple[CodeAction, ...]:
        doc = self.documents.get(uri)
        if doc is None:
            return ()
        actions: list[CodeAction] = []
        for diag in doc.diagnostics:
            d_start_line = diag.location.range.start.line
            d_end_line = diag.location.range.end.line
            if not (range_obj.start.line <= d_end_line and range_obj.end.line >= d_start_line):
                continue
            data = diag.data or {}
            fix_candidates = data.get("fix_candidates", [])
            for idx, fix in enumerate(fix_candidates):
                title = fix.get("title") or "Apply suggested fix"
                edits: list[TextEdit] = []
                if "span" in fix and "replacement" in fix:
                    span = fix["span"]
                    start_dict = span.get("start", {})
                    end_dict = span.get("end", {})
                    s_line = max(int(start_dict.get("line", 1)) - 1, 0)
                    s_col = max(int(start_dict.get("column", 1)) - 1, 0)
                    e_line = max(int(end_dict.get("line", 1)) - 1, 0)
                    e_col = max(int(end_dict.get("column", 1)) - 1, 0)
                    edit_rng = Range(Position(s_line, s_col), Position(e_line, e_col))
                    edits.append(TextEdit(edit_rng, fix.get("replacement", "")))
                elif "edits" in fix:
                    for edit_info in fix.get("edits", []):
                        span = edit_info.get("span", {})
                        start_dict = span.get("start", {})
                        end_dict = span.get("end", {})
                        s_line = max(int(start_dict.get("line", 1)) - 1, 0)
                        s_col = max(int(start_dict.get("column", 1)) - 1, 0)
                        e_line = max(int(end_dict.get("line", 1)) - 1, 0)
                        e_col = max(int(end_dict.get("column", 1)) - 1, 0)
                        edit_rng = Range(Position(s_line, s_col), Position(e_line, e_col))
                        edits.append(TextEdit(edit_rng, edit_info.get("new_text", "")))
                elif "replacement" in fix:
                    edits.append(TextEdit(diag.location.range, fix["replacement"]))

                ws_edit = WorkspaceEdit(changes={uri: edits}) if edits else None
                actions.append(
                    CodeAction(
                        title=title,
                        kind="quickfix",
                        diagnostics=(diag,),
                        is_preferred=(idx == 0),
                        edit=ws_edit,
                    )
                )
        return tuple(actions)

    def references(self, uri: str, line: int, character: int) -> tuple[Location, ...]:
        document = self.documents.get(uri)
        if document is None:
            return ()
        token = _word_at(document.text, line, character)
        if token is None:
            return ()
        symbol = self._resolve_token(uri, token.text, line, token.range.start.character)
        name = symbol.name if symbol is not None else token.text.split(".")[-1]
        locations: list[Location] = []
        for state in self.documents.values():
            # Mask out block comments preserving newlines and character offsets
            def mask_block(m: re.Match[str]) -> str:
                return "".join("\n" if c == "\n" else " " for c in m.group(0))

            masked_text = re.sub(r"/\*.*?\*/", mask_block, state.text, flags=re.DOTALL)
            for line_number, raw_line in enumerate(masked_text.splitlines()):
                line_no_comment = raw_line.split("//", 1)[0]
                for match in re.finditer(rf"\b{re.escape(name)}\b", line_no_comment):
                    locations.append(
                        Location(
                            state.uri,
                            range_for(line_number, match.start(), name),
                        )
                    )
        return tuple(locations)

    def workspace_symbols(self, query: str = "") -> tuple[Symbol, ...]:
        indexed = [symbol for symbols in self.symbols.values() for symbol in symbols]
        all_syms = [*indexed, *BUILTIN_SYMBOLS]
        if not query:
            return tuple(all_syms)
        q_lower = query.lower()
        return tuple(s for s in all_syms if q_lower in s.name.lower())

    def signature_help(self, uri: str, line: int, character: int) -> SignatureHelp | None:
        doc = self.documents.get(uri)
        if doc is None:
            return None
        return _extract_signature_help(doc.text, line, character, self)

    def semantic_tokens(self, uri: str) -> SemanticTokens | None:
        doc = self.documents.get(uri)
        if doc is None:
            return None
        data = _extract_semantic_tokens(doc.text)
        return SemanticTokens(data=data)

    def prepare_rename(self, uri: str, line: int, character: int) -> Range | None:
        doc = self.documents.get(uri)
        if doc is None:
            return None
        token = _word_at(doc.text, line, character)
        if token is None:
            return None
        if token.text in KEYWORD_METADATA or token.text in API_METADATA or token.text in ("true", "false", "int", "string", "bool", "float"):
            return None
        for b in BUILTIN_SYMBOLS:
            if b.name == token.text:
                return None
        return token.range

    def rename(self, uri: str, line: int, character: int, new_name: str) -> WorkspaceEdit | None:
        if not new_name or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", new_name):
            return None
        if new_name in KEYWORD_COMPLETIONS or new_name in ("world", "system", "component"):
            return None

        doc = self.documents.get(uri)
        if doc is None:
            return None
        token = _word_at(doc.text, line, character)
        if token is None:
            return None

        if token.text in KEYWORD_METADATA or token.text in API_METADATA:
            return None
        for b in BUILTIN_SYMBOLS:
            if b.name == token.text:
                return None

        for sym in self.workspace_symbols():
            if sym.name == new_name and sym.location.uri == uri:
                return None

        refs = self.references(uri, line, character)
        if not refs:
            return None

        changes: dict[str, list[TextEdit]] = {}
        for loc in refs:
            if loc.uri not in changes:
                changes[loc.uri] = []
            changes[loc.uri].append(TextEdit(loc.range, new_name))

        return WorkspaceEdit(changes=changes)

    def formatting(self, uri: str, options: FormattingOptions | None = None) -> tuple[TextEdit, ...]:
        doc = self.documents.get(uri)
        if doc is None:
            return ()
        formatted = _format_reasonscript(doc.text, options)
        if formatted == doc.text:
            return ()
        lines = doc.text.splitlines()
        end_line = max(len(lines) - 1, 0)
        end_col = len(lines[-1]) if lines else 0
        full_range = Range(Position(0, 0), Position(end_line + 1, 0))
        return (TextEdit(full_range, formatted),)

    def _analyze(self, uri: str, text: str, version: int) -> DocumentState:
        from frontend.compiler_frontend import CompilerFrontend, FrontendRequest

        req = FrontendRequest(source=text, filename=uri, uri=uri, compiler_mode="lsp")
        result = CompilerFrontend.analyze(req)

        lsp_diagnostics: list[Diagnostic] = []
        for d in result.diagnostics:
            line = max((d.location.line or 1) - 1, 0)
            col = max((d.location.column or 1) - 1, 0)
            length = d.location.length or 1
            rng = Range(Position(line, col), Position(line, col + length))
            severity = (
                DiagnosticSeverity.ERROR
                if d.severity == "ERROR"
                else DiagnosticSeverity.WARNING
                if d.severity == "WARNING"
                else DiagnosticSeverity.INFORMATION
            )
            fixes_payload = [f.to_dict() for f in d.fixes] if d.fixes else ([d.fix.to_dict()] if d.fix else [])
            data_payload = {
                "title": d.title,
                "help": d.help,
                "fix_candidates": fixes_payload,
            } if (d.title or d.help or fixes_payload) else None
            lsp_diagnostics.append(
                Diagnostic(
                    severity=severity,
                    code=DiagnosticCode(d.code),
                    message=d.message,
                    location=Location(uri, rng),
                    data=data_payload,
                )
            )

        symbols = _scan_symbols(uri, text)
        state = DocumentState(uri, version, text, result.ast, tuple(lsp_diagnostics), symbols)
        self.documents[uri] = state
        self.symbols[uri] = symbols
        return state

    def _resolve_token(self, uri: str, token: str, line: int, character: int = 0) -> Symbol | None:
        for b_sym in BUILTIN_SYMBOLS:
            if b_sym.name == token:
                return b_sym
        name = token.split(".")[-1].split("::")[-1]

        qualifier: str | None = None
        doc = self.documents.get(uri)
        if doc and 0 <= line < len(doc.text.splitlines()):
            line_str = doc.text.splitlines()[line]
            prefix = line_str[:max(character, 0)].rstrip()
            q_match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)(?:\.|\:\:)$", prefix)
            if q_match:
                qualifier = q_match.group(1)

        doc_text = doc.text if doc is not None else ""
        module = _module_for_line(doc_text, line)
        all_symbols = self.workspace_symbols()

        if qualifier:
            qualified_symbols = [
                s for s in all_symbols
                if s.name == name and (s.module == qualifier or s.module.endswith(f".{qualifier}"))
            ]
            if qualified_symbols:
                return qualified_symbols[0]

        symbols = [
            symbol
            for symbol in all_symbols
            if symbol.name == name or symbol.module == token
        ]
        if not symbols:
            return None
        same_module = [symbol for symbol in symbols if symbol.module == module]
        if same_module:
            return same_module[0]
        same_file = [symbol for symbol in symbols if symbol.location.uri == uri]
        if same_file:
            return same_file[0]
        public = [symbol for symbol in symbols if symbol.visibility == "Public"]
        return public[0] if public else symbols[0]
