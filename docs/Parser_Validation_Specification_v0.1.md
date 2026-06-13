# Parser Validation Specification v0.1

Status: Implemented Draft
Parser contract: `parser/0.1`
Output ABI: `reasonscript-ast/0.1`
Encoding: UTF-8

## Purpose

The Phase 2 parser is the deterministic boundary from replaceable source
syntax to the stable semantic AST ABI.

```text
Source -> Lexer -> Token Stream -> Parser -> AST Builder -> AST ABI
```

The parser does not import Runtime code and does not produce Reason IR.
Compiler optimization, macros, type checking, and language server protocols
are outside Phase 2.

This minimal frontend syntax is separate from the pre-existing legacy runtime
grammar documented in `docs/grammar.md`.

## Minimal Grammar

```ebnf
module       ::= (statement NEWLINE*)* EOF
statement    ::= goal | state | transition | constraint | context | import
goal         ::= "goal" atom
state        ::= "state" atom
transition   ::= "transition" atom atom atom
constraint   ::= "constraint" atom
context      ::= "context" URI
import       ::= "import" (atom | URI)
atom         ::= Identifier | String
```

Statements are line-oriented. Empty lines are allowed. Comments, blocks,
macros, multiline strings, and statement continuations are not supported.

## Lexer Contract

The lexer emits immutable tokens with `token_type`, `value`, one-based `line`,
and one-based `column`.

Token types:

- `Keyword`
- `Identifier`
- `String`
- `Number`
- `URI`
- `NewLine`
- `EOF`

Reserved keywords are `goal`, `state`, `transition`, `constraint`, `context`,
and `import`. Identifiers are non-empty UTF-8 tokens without whitespace.
Single- and double-quoted strings are supported on one line. A URI token must
contain an explicit scheme followed by `://`.

## Parser Contract

`parse(source: str) -> ModuleNode` requires:

- exactly one `goal` statement
- exactly one initial `state` statement
- zero or more transitions
- zero or more constraints
- zero or more contexts
- zero or more imports

Unknown keywords and extra or missing arguments are errors. Reserved keywords
cannot be used as unquoted statement arguments.

## AST Builder Defaults

The minimal syntax omits fields already fixed by the semantic contract. The
builder supplies them deterministically:

| Source | AST fields |
|---|---|
| `goal X` | `kind = "reach_state"`, `target = X` |
| `state X` | `state_id = X`, `state_type = "symbolic"`, `data = {}` |
| `transition A R B` | source/relation/target, cost `1.0` |
| `constraint X` | ID derived from X, `kind = "predicate"`, expression X |
| `context scheme://X` | context type from scheme, ID from scheme and authority |
| `import X` | append X to `ModuleNode.imports` |

The module ID is `module`. Declaration node IDs are `<kind>-<occurrence>`.
Transition IDs are `<source>-<relation>-<target>` with a numeric suffix for
repeated identical declarations. These rules make source-to-AST conversion
stable and independent of process state.

## Error Model

`ParserError` contains:

```text
code
line
column
message
severity
```

All Phase 2 errors have severity `error`. Codes are grouped by category:

| Category | Codes |
|---|---|
| Syntax | `syntax.unknown_keyword`, `syntax.missing_argument`, `syntax.malformed_statement`, `syntax.unterminated_string` |
| Semantic | `semantic.duplicate_goal`, `semantic.duplicate_initial_state`, `semantic.missing_goal`, `semantic.missing_initial_state`, `semantic.invalid_uri` |
| Validation | `validation.ast_abi` |

The parser fails on the first error and reports the source location of the
offending token or end of input for missing module declarations.

## AST ABI Invariant

Every successful parse is passed through the Phase 0 semantic validator.
Conformance additionally serializes it and validates it against
`frontend/schemas/ast.schema.json`. Therefore every successful parser result
is a valid `reasonscript-ast/0.1` document.

## Fixtures

Valid fixtures:

- `basic_inference.rsn`
- `constraint.rsn`
- `context.rsn`
- `tool_integration.rsn`
- `worldmodel_transition.rsn`
- `dbm_planning.rsn`

Invalid fixtures:

- `missing_goal.rsn`
- `missing_state.rsn`
- `duplicate_goal.rsn`
- `invalid_transition.rsn`
- `invalid_uri.rsn`
- `unknown_keyword.rsn`

## Conformance Layers

| Layer | Validation |
|---:|---|
| 0 | Source to positioned token stream |
| 1 | Token stream to deterministic AST and structured errors |
| 2 | Generated AST against the AST ABI validator |
| 3 | Generated AST to schema-valid Reason IR |
| 4 | Source through reference inference result |

Run all layers with:

```sh
python3 frontend/parser_conformance/run_conformance.py
```

Parse one source file with:

```sh
python3 -m frontend.parser source.rsn
```

## Phase 2 Decision

The line-oriented syntax and reference parser are sufficient to validate the
Source-to-AST contract without freezing future ReasonScript syntax. Phase 3
may consume only the AST ABI and must not depend on lexer or parser internals.
