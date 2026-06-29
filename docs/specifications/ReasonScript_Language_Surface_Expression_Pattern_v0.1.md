# ReasonScript Language Surface Phase 1.2

## Expression & Pattern Specification v0.1

Status: VALIDATED FOR THE DEFINED PHASE 1.2 SURFACE

Compatible interfaces:

- `reasonscript-language-surface/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `reason-ir/0.1`
- `execution-plan/0.1`

## 1. Purpose

Phase 1.2 replaces the opaque Phase 1.1 representations:

```text
ExpressionNode("income * factor")
PatternNode("Draft")
```

with immutable structural AST values:

```text
Source Expression -> ExpressionNode -> Expression hierarchy
Source Pattern    -> PatternNode    -> Pattern hierarchy
```

This phase fixes parsing, precedence, AST shape, validation, serialization,
and compiler projection. Evaluation, optimization, type inference, operator
overloading, lambdas, closures, macros, and Runtime execution are excluded.

## 2. Root Models

```text
ExpressionNode {
  expression: Expression
}

PatternNode {
  pattern: Pattern
}
```

Every node is immutable. Every serialized node has a `node_type`
discriminator.

## 3. Literal and Identifier Expressions

| Source | Node | Value contract |
|---|---|---|
| `42` | `IntegerLiteralNode` | signed int64 |
| `3.14` | `FloatLiteralNode` | finite float64 |
| `true`, `false` | `BooleanLiteralNode` | boolean |
| `"hello"` | `StringLiteralNode` | string |
| `null` | `NullLiteralNode` | no payload |
| `score` | `IdentifierNode` | AST-V002 identifier |

Negative numbers are represented as `UnaryExpressionNode(Negate, literal)`,
not as negative literal tokens.

## 4. Unary Expressions

```text
-score -> UnaryExpressionNode(Negate, IdentifierNode("score"))
!valid -> UnaryExpressionNode(Not, IdentifierNode("valid"))
```

Supported `UnaryOperator` values are `Negate` and `Not`.

## 5. Binary Arithmetic Expressions

`BinaryExpressionNode` contains `left`, `operator`, and `right`.

| Surface | BinaryOperator |
|---|---|
| `+` | `Add` |
| `-` | `Subtract` |
| `*` | `Multiply` |
| `/` | `Divide` |
| `%` | `Modulo` |

All binary operators are left-associative.

## 6. Comparison Expressions

`ComparisonExpressionNode` supports:

| Surface | ComparisonOperator |
|---|---|
| `==` | `Equal` |
| `!=` | `NotEqual` |
| `>` | `GreaterThan` |
| `>=` | `GreaterThanOrEqual` |
| `<` | `LessThan` |
| `<=` | `LessThanOrEqual` |

Comparison chaining is not a distinct Phase 1.2 construct. Repeated operators
associate left according to the common parser rule.

## 7. Logical Expressions

`LogicalExpressionNode` supports:

```text
&& -> And
|| -> Or
```

`And` binds more tightly than `Or`.

## 8. Parenthesized Expressions

Explicit grouping is preserved:

```text
(a + b)
  -> ParenthesizedExpressionNode(
       BinaryExpressionNode(a, Add, b)
     )
```

Parentheses affect parsing and remain observable in serialization.

## 9. Member Access and Calls

Member access:

```text
user.profile.age
```

becomes nested `MemberAccessNode` values. Every member is a valid identifier.

Calls:

```text
risk(score, age)
```

become:

```text
CallExpressionNode {
  callee: IdentifierNode("risk")
  arguments: (IdentifierNode("score"), IdentifierNode("age"))
}
```

The callee may itself be a member access or call expression. Empty argument
lists are valid. Trailing commas are not supported in Phase 1.2.

## 10. Operator Precedence

The parser uses these binding levels, highest first:

| Level | Constructs |
|---:|---|
| 80 | member access, call |
| 70 | unary negate, logical not |
| 60 | multiply, divide, modulo |
| 50 | add, subtract |
| 40 | comparisons |
| 30 | logical And |
| 20 | logical Or |

The implementation uses deterministic precedence climbing. For example:

```text
1 + 2 * 3
```

maps to:

```text
Binary(Add,
  Integer(1),
  Binary(Multiply, Integer(2), Integer(3)))
```

## 11. Pattern Hierarchy

Supported patterns are:

```text
IdentifierPatternNode { name }
WildcardPatternNode
LiteralPatternNode { value: Literal }
```

Examples:

| Source | Pattern |
|---|---|
| `Draft` | identifier |
| `_` | wildcard |
| `1` | integer literal |
| `true` | boolean literal |
| `"ok"` | string literal |
| `null` | null literal |

Expressions, calls, member access, unary operators, and binary operators are
not valid Phase 1.2 patterns.

## 12. Match Mapping

The Surface parser now parses both the match expression and each arm pattern:

```text
match state {
  Draft => approve()
  Approved => publish()
  _ => reject()
}
```

The arm order is preserved. The three patterns become two
`IdentifierPatternNode` values followed by one `WildcardPatternNode`.

## 13. Validation

Expression validation:

| Rule | Requirement |
|---|---|
| EX-V001 | Known expression node and valid literal payload |
| EX-V002 | Operator is a member of the correct operator enum |
| EX-V003 | Parentheses are balanced and non-empty |
| EX-V004 | Call arguments and delimiters are valid |
| EX-V005 | Member access has a valid member identifier |

Pattern validation:

| Rule | Requirement |
|---|---|
| PT-V001 | Pattern exists and has a known type |
| PT-V002 | `_` uses `WildcardPatternNode` |
| PT-V003 | Literal pattern contains a supported literal |
| PT-V004 | Identifier pattern satisfies AST-V002 |

Parser errors are raised before Surface AST validation. Manually constructed
AST values are independently checked by the validator.

## 14. Serialization

The normative schemas are:

- `frontend/schemas/expression.schema.json`
- `frontend/schemas/pattern.schema.json`
- expression and pattern definitions embedded in
  `frontend/schemas/language_surface_ast.schema.json`

Round trips are structural:

```text
expression_from_json(to_json_value(expression)) == expression
pattern_from_json(to_json_value(pattern)) == pattern
```

## 15. Surface Parser Integration

Every Phase 1.1 expression position now invokes the Phase 1.2 parser:

- Let right-hand side;
- assignment right-hand side;
- calculation Result;
- if and elif condition;
- match subject;
- transition and branch call statements.

Every match arm invokes the Phase 1.2 pattern parser. No expression or pattern
is retained as opaque text in the Surface AST.

## 16. Semantic AST Projection

The existing `reasonscript-ast/0.1` ABI is unchanged. Structured expressions
are serialized into existing semantic Transition `effect` data:

```text
effect {
  calculation,
  target,
  expression: {
    node_type: "ExpressionNode",
    expression: ...
  }
}
```

The root expression type selects the relation:

| Root expression | Semantic relation |
|---|---|
| arithmetic binary | matching arithmetic Transition |
| comparison | `CompareTransition` |
| logical | `LogicalTransition` |
| unary | `UnaryTransition` |
| member access | `MemberAccessTransition` |
| call | `CallTransition` |
| literal, identifier, parenthesized | `ExpressionTransition` |

This preserves structure for later compiler phases without adding a Reason IR
field or changing Runtime behavior.

## 17. Conformance

Implementation:

- `frontend/language_surface/expressions.py`
- `frontend/language_surface/nodes.py`
- `frontend/language_surface/parser.py`
- `frontend/language_surface/validation.py`
- `frontend/language_surface/integration.py`

Validation:

```sh
python3 -m unittest discover \
  -s expression_pattern_tests -p 'test_*.py' -v
```

Phase 1.1 and all existing platform regressions remain mandatory.
