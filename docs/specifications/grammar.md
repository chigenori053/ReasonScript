# ReasonScript Formal Grammar v1

This document is the authoritative surface syntax contract for ReasonScript v1.
It formalizes the current line-based parser behavior without redesigning the
implementation.

## EBNF

```ebnf
program     ::= statement*

statement   ::= goal
              | derive
              | prove
              | apply
              | compute
              | converge
              | rollback

goal        ::= "goal" WS symbol
derive      ::= "derive" WS symbol
prove       ::= "prove" WS proof
apply       ::= "apply" WS value
compute     ::= "compute" WS value WS operator WS value
converge    ::= "converge" WS symbol
rollback    ::= "rollback" WS state
```

## Lexical Categories

```ebnf
symbol      ::= IDENT
proof       ::= IDENT
state       ::= IDENT
value       ::= symbol | nat | int | rational
nat         ::= DIGIT+
int         ::= "-" DIGIT+
rational    ::= int? DIGIT+ "/" DIGIT+
operator    ::= "+" | "-"
IDENT       ::= LETTER (LETTER | DIGIT | "_")*
WS          ::= " "+
```

## Notes

- Statements are single-line only.
- Newlines terminate statements.
- Empty lines are allowed.
- Unknown keywords are ignored by the current parser implementation.
- The parser currently splits each line with `splitn(2, ' ')` and trims the
  remainder as the payload.

## AST Correspondence

Grammar and AST must remain in 1:1 correspondence:

- `goal` -> `Statement::Goal(Symbol)`
- `derive` -> `Statement::Derive(Symbol)`
- `prove` -> `Statement::Prove(Proof)`
- `apply` -> `Statement::Apply(Value)`
- `compute` -> `Statement::Compute(BinaryOp)`
- `converge` -> `Statement::Converge(Symbol)`
- `rollback` -> `Statement::Rollback(State)`

## Value Examples

- `apply 42` -> `Value::Nat(42)`
- `apply -3` -> `Value::Int(-3)`
- `apply 1/2` -> `Value::Rational(1, 2)`
- `apply x` -> `Value::Symbol(Symbol("x"))`
- `compute 1/2 + 3/4` -> `Statement::Compute(BinaryOp::Add(...))`

The parser classifies `apply` payloads in this order:

1. rational
2. int
3. nat
4. symbol

Blocks, imports, comments, strings, and multiline syntax remain out of scope.
