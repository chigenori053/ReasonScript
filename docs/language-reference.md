# ReasonScript language reference

This is the canonical human-readable reference for the source language shipped
with ReasonScript v0.5.5.10 (language core `0.7`). It documents accepted `.rsn`
syntax and observable execution behavior, not compiler implementation phases.

## Program structure

A source unit contains an optional package declaration followed by one or more
modules. `model` is accepted as a source-level synonym for `module`; both lower
to the same semantics.

```reason
package demo

module Geometry {
  // declarations
}

model Planning {
  import Geometry
}
```

Names start with a letter or underscore and continue with letters, digits, or
underscores. Imports use dotted module names and may have a local alias:

```reason
import tools.geometry
import tools.statistics as stats
```

`//` starts a line comment outside a string. Braces delimit blocks. Statements
normally end at a newline; a trailing `\` or an open parenthesis continues a
statement onto the next physical line. Semicolons are not statement
terminators. `world`, `system`, and `component` are reserved, not active
top-level declarations.

## A complete small program

```reason
module Scores {
  struct Student {
    name: string
    score: int
  }

  enum Grade {
    Pass
    Fail
  }

  fn GradeFor(score: int) -> Grade {
    if score >= 60 {
      return Grade.Pass
    } else {
      return Grade.Fail
    }
  }

  calculation Result -> string {
    let student = Student { name: "Ada", score: 91 }
    match GradeFor(student.score) {
      Grade.Pass => result = student.name
      Grade.Fail => result = ""
    }
  }
}
```

A `calculation` is an executable named entry. Its `result =` statement is the
observable value reported by the runtime. A function returns with `return`.

## Types

Primitive types are `int`, `float`, `bool`, `string`, and `null`. The capitalized
forms `Int`, `Float`, `Bool`, `String`, and `Null` are also recognized in the
type model. Additional state kinds are `Concept`, `Object`, `Event`, `Action`,
`Attribute`, `Goal`, and `Constraint`.

Composite types are:

| Type | Example |
| --- | --- |
| Array | `[int]` |
| Tuple | `(string, int)` |
| Set | `set<string>` |
| Map | `map<string, int>` |
| Optional | `optional<int>` |
| User-defined | `Student`, `Grade` |
| Runtime object | `Tensor`, `ReasonObject` |

Type annotations are required on typed function parameters and may be used on
bindings, function results, and calculations:

```reason
let attempts: int = 3
const ratio: float = 0.5

fn Clamp(value: int, minimum: int, maximum: int) -> int {
  // ...
}

calculation Answer -> int {
  result = 42
}
```

`int(value)` truncates a numeric value toward zero. `float(value)` converts a
numeric value to floating point. A user-declared function with either name
shadows the built-in cast.

## Literals and expressions

```reason
42
-7
3.14
1.0e-6
true
false
"text"
'text'
null
none
some(42)
[1, 2, 3]
("Ada", 91)
Student { name: "Ada", score: 91 }
```

Multiline sets and maps are supported in binding, `return`, and `result`
positions:

```reason
let tags: set<string> = set {
  "stable"
  "native"
}

let scores: map<string, int> = map {
  "Ada": 91
  "Lin": 88
}
```

Arrays, maps, and tuples support indexing where their type permits it. Structs
support field access. Assignments may update a mutable binding, field, or
index:

```reason
value = value + 1
student.score = 100
values[0] = 100
```

### Operators

From highest to lowest precedence:

| Operators | Meaning |
| --- | --- |
| `-x`, `!x` | numeric negation, logical not |
| `*`, `/`, `%` | multiplication, true division, floor-compatible remainder |
| `+`, `-` | addition, subtraction |
| `==`, `!=`, `>`, `>=`, `<`, `<=` | comparison |
| `&&` | logical and |
| `||` | logical or |

Operators of equal precedence associate left to right. Parentheses override
precedence. `/` always produces a `float`, including for two integer operands.
`//` is a comment token and is not integer division.

Calls, member access, and indexing bind more tightly than these operators:

```reason
Normalize(rows[0].score)
tensor.mean(values, 0, false)
tools.math::Average(values)
```

Qualified imported symbols use `::`. A dot denotes member access or a built-in
namespace call.

## Bindings and constants

`let` creates a local binding that may be assigned again. `const` creates an
immutable value. A module-level constant is visible throughout its module.

```reason
const Threshold: int = 60

calculation Passed -> bool {
  let score = 91
  score = score + 1
  result = score >= Threshold
}
```

Use `export` for public structs, enums, constants, functions, and calculations.
`pub` is also accepted for modules, functions, and calculations. Export
modifiers are only valid at module scope.

## Structs and enums

```reason
export struct Point {
  x: float
  y: float
}

export enum Direction {
  North
  East
  South
  West
}

const Origin = Point { x: 0.0, y: 0.0 }
```

Every struct field requires a type. Enum variants are referenced as
`Direction.North`.

## Functions and calculations

```reason
fn DistanceSquared(x: float, y: float) -> float {
  return x * x + y * y
}

calculation Distance goal:Ready -> float {
  result = DistanceSquared(3.0, 4.0)
}
```

Functions may call functions and read visible constants. Recursion and loops
are bounded by runtime limits. Every reachable path of a non-void function must
return a compatible value. A calculation should produce one compatible
`result`; dependencies between calculations are resolved deterministically and
cycles are rejected.

## Control flow

### Conditions

```reason
if score >= 90 {
  result = "A"
} elif score >= 80 {
  result = "B"
} else {
  result = "C"
}
```

Conditions must be Boolean. `else` is optional.

### Loops

```reason
for item in values {
  total = total + item
}

while index < 10 {
  index = index + 1
}

loop {
  if done {
    break
  }
  continue
}
```

`break` and `continue` are valid only inside a loop. Runtime iteration and call
limits turn accidental infinite execution into a structured diagnostic.

### Pattern matching

```reason
match value {
  0 => return "zero"
  1..9 => return "digit"
  10..<100 when enabled => return "two digits"
  some(item) => return "present"
  none => return "absent"
  default => return "other"
}
```

Supported patterns include literals, enum variants, identifiers, `_`,
`default`, inclusive ranges (`a..b`), upper-exclusive ranges (`a..<b`),
`some(pattern)`, `none`, struct patterns, and alternatives separated by `|`.
A `when` guard is evaluated after its pattern matches.

```reason
match point {
  Point { x: 0, y } => return y
  Point { x, y: 0 } | Point { x: 0, y } => return 0
  default => return -1
}
```

Matches over closed types such as enums and optionals are checked for
exhaustiveness. `default` and `_` provide a fallback. Alternatives must bind a
compatible set of names.

## Reasoning declarations

The language also has declarative reasoning constructs:

```reason
module Route {
  state Start
  state Finish
  goal Finish
  constraint Safe

  transition Move {
    Start -> Finish
    requires Safe
  }

  reason_graph Main {
    state Start
    state Finish
    transition Start -> Finish
  }

  execution_plan Direct {
    step Start -> Finish
  }
}
```

`concept`, `object`, `event`, `action`, and `attribute` introduce named
semantic entities. Relations are written as `Subject Relation Object`, where
the relation is one of `IsA`, `PartOf`, `Cause`, `Dependency`, `Constraint`,
`Temporal`, `Spatial`, or `Similar`.

Inside executable blocks, `require Name`, `goal Name`, and `reach Name` record
the corresponding reasoning intent.

## Built-in namespaces

ReasonScript exposes functionality through qualified calls rather than hidden
ambient behavior:

- `runtime.*` — input/output and reasoning operations.
- `tensor.*` — Tensor creation, shape, math, reduction, linear algebra,
  inference, autograd, random generation, conversion, and file I/O.
- `optimizer.*` — pure SGD, Momentum, Adam, and AdamW update functions.
- `relation.*` — filtering, counting, sorting, and deduplication over arrays of
  structs.
- `string.*` — string operations.
- `vision.*` — deterministic Vision runtime integration.
- `ruo.*` — ReasonUnit Object inspection, snapshots, queries, and transactions.

See the [standard library reference](standard-library.md) for the public
surface. File-reading and file-writing calls require explicit runtime
capabilities such as `--allow-read` and `--allow-write`.

## Execution and diagnostics

`reason check` parses, resolves, and type-checks source without running it.
`reason build` writes project build artifacts. `reason run` executes a source
file or previously built project with the native Rust host.

```sh
reason check program.rsn --json
reason run program.rsn --json
```

Diagnostics carry stable families such as parser, type, Tensor (`TSF`),
autograd (`AD`), optimizer (`OPT`), and runtime (`RT`) codes. Use JSON output in
tools and agents instead of parsing human-formatted text.

Execution is deterministic for the same source, inputs, capabilities, and
runtime configuration. Array and struct assignments preserve reference/alias
semantics. Tensor values are opaque handles; convert them explicitly with
`tensor.scalar` or `tensor.to_array` when a plain result is needed.

## Compatibility and known limits

- Named arguments are limited; `optimizer.*` and `relation.*` are positional
  only. Tensor named arguments, where accepted, must follow signature order.
- A trailing comma is not accepted in arrays, tuples, or calls.
- `//` cannot be used for integer division because it begins a comment.
- Runtime filesystem and resource limits are enforced even when source is
  statically valid.
- Some artifact and graph commands are CLI operations, not language syntax.

See [known limitations](releases/ReasonScript_v0_5_Known_Limitations.md) for
release-specific constraints.

## Reference map for implementers and agents

This document is the prose source-language contract. For exact machine-facing
interfaces, use:

- `frontend/language_surface/` — parser, nodes, name resolution, and validation.
- `schemas/` — JSON schemas for serialized interfaces.
- `contracts/tensor_function_manifest.json` — frozen Tensor call contract.
- `contracts/runtime_consolidation_manifest.json` — native runtime coverage.
- `examples/` and `fixtures/` — executable examples.
- `golden/` — expected observable behavior.

Do not infer current behavior from old release plans or implementation reports.
