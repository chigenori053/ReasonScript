# ReasonScript Language Surface Phase 1.2

## Expression & Pattern Validation Report v0.1

Status: PASS

Validation date: 2026-06-14

Target: structured Expression and Pattern AST mapping

## 1. Executive Result

Phase 1.2 is complete for the defined surface. Expression and Pattern values
are no longer opaque strings. The parser produces immutable structural nodes,
operator precedence is deterministic, invalid syntax is rejected, and JSON
round trips preserve exact node structure.

Structured Calculation expressions project into the existing semantic AST
and compile to schema-valid `reason-ir/0.1` without interface changes.

## 2. Deliverables

| Artifact | Result |
|---|---|
| `docs/ReasonScript_Language_Surface_Expression_Pattern_v0.1.md` | CREATED |
| `frontend/language_surface/expressions.py` | CREATED |
| Expression hierarchy in `frontend/language_surface/nodes.py` | COMPLETED |
| Pattern hierarchy in `frontend/language_surface/nodes.py` | COMPLETED |
| `frontend/schemas/expression.schema.json` | CREATED |
| `frontend/schemas/pattern.schema.json` | CREATED |
| Surface AST schema expression/pattern definitions | UPDATED |
| `expression_pattern_tests/` | CREATED |
| This validation report | CREATED |

## 3. Layer A: Expression Nodes

| ID | Result |
|---|---|
| A-001 Integer Literal | PASS |
| A-002 Float Literal | PASS |
| A-003 Boolean Literal | PASS |
| A-004 String Literal | PASS |
| A-005 Identifier | PASS |
| A-006 Unary | PASS |
| A-007 Binary | PASS |
| A-008 Comparison | PASS |
| A-009 Logical | PASS |
| A-010 Member Access | PASS |
| A-011 Call | PASS |
| A-010 Member Access | PASS |
| A-011 Call | PASS |

Null literal support was also validated.

## 4. Layer B: Operator Precedence

| ID | Result |
|---|---|
| B-001 Unary | PASS |
| B-002 Multiply Before Add | PASS |
| B-003 Comparison After Arithmetic | PASS |
| B-004 Logical After Comparison | PASS |
| B-005 Parentheses Override | PASS |

Parenthesized grouping remains represented by a dedicated node.

## 5. Layer C: Patterns

| ID | Result |
|---|---|
| C-001 Identifier Pattern | PASS |
| C-002 Literal Pattern | PASS |
| C-003 Wildcard Pattern | PASS |
| C-004 Match Arm Mapping | PASS |

Match arm source order is preserved.

## 6. Layer D: Invalid Syntax

| ID | Result |
|---|---|
| D-001 Missing Operand | PASS, rejected |
| D-002 Invalid Operator | PASS, rejected |
| D-003 Unbalanced Parentheses | PASS, rejected |
| D-004 Invalid Member Access | PASS, rejected |
| D-005 Invalid Call | PASS, rejected |
| D-006 Empty Pattern | PASS, rejected |

Invalid operator values in manually constructed AST objects are also rejected
by EX-V002.

## 7. Layer E: Compiler Compatibility

| ID | Result |
|---|---|
| E-001 Expression Serialization | PASS |
| E-002 Expression Round Trip | PASS |
| E-003 Pattern Round Trip | PASS |
| E-004 Semantic AST Projection | PASS |
| E-005 Reason IR Generation | PASS |

The semantic Transition effect contains the structured serialized expression.
Arithmetic roots select explicit arithmetic Transition relations.

## 8. Validation Rules

| Rule | Result |
|---|---|
| EX-V001 Known Expression Type | PASS |
| EX-V002 Operator Validity | PASS |
| EX-V003 Parenthesis Balance | PASS |
| EX-V004 Call Syntax Validity | PASS |
| EX-V005 Member Access Validity | PASS |
| PT-V001 Pattern Exists | PASS |
| PT-V002 Wildcard Usage Valid | PASS |
| PT-V003 Literal Pattern Valid | PASS |
| PT-V004 Identifier Pattern Valid | PASS |

## 9. Compatibility Audit

No version or field change was made to:

- `reasonscript-ast/0.1`;
- `parser/0.1`;
- `compiler/0.1`;
- `reason-ir/0.1`;
- `execution-plan/0.1`;
- HybridRuntime.

The change is confined to the additive Language Surface frontend introduced
in Phase 1.1. Existing semantic AST consumers continue to receive the same
node classes and Reason IR shape.

## 10. Scope Boundary

The phase does not evaluate expressions. It does not define types, coercion,
operator overloading, lambdas, closures, macros, generics, optimization, or
Runtime execution behavior.

Expression and Pattern structure is now sufficient for later statement,
typing, and calculation lowering phases.

## 11. Verification Record

Phase 1.2 validation:

```text
Ran 18 tests
OK
```

Phase 1.1 regression:

```text
Ran 16 tests
OK
```

Complete Python regression:

```text
Ran 148 tests
OK (skipped=1)
```

The skip is the pre-existing optional Go adapter comparison because the Go
toolchain is not installed.

HybridRuntime regression:

```text
129 passed
0 failed
```

`python3 -m py_compile` and `git diff --check` completed without errors.

## 12. Exit Decision

The Phase 1.2 exit criteria are satisfied:

- Expression AST fixed;
- Pattern AST fixed;
- operator precedence fixed;
- validation rules fixed;
- parser tests pass;
- serialization tests pass;
- compiler compatibility passes;
- Reason IR generation passes.

Phase 1.3 Statement Specification may proceed without an existing platform
interface version change.
