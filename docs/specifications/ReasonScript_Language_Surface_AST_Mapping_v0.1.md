# ReasonScript Language Surface Phase 1.1

## AST Mapping Specification v0.1

Status: VALIDATED FOR THE DEFINED PHASE 1.1 SURFACE

Compatible interfaces:

- `reasonscript-language-surface/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `reason-ir/0.1`

## 1. Purpose

This specification fixes the deterministic correspondence:

```text
Source Code
  -> Surface Parser
  -> immutable Surface AST
  -> Semantic AST reasonscript-ast/0.1
  -> Compiler 0.1
  -> Reason IR 0.1
```

It defines syntax representation and compiler integration. Runtime execution
meaning, planner selection, optimization, macros, and machine execution are
outside Phase 1.1.

## 2. Compatibility Architecture

The previously validated `reasonscript-ast/0.1` ABI has one `ModuleNode` as
the root of one compilation unit. Phase 1.1 introduces a source-facing
`ProgramNode` that can contain multiple modules.

Replacing the existing root would break `parser/0.1`, `compiler/0.1`, AST JSON
fixtures, and Reason IR lowering. Therefore Phase 1.1 uses two explicit
levels:

```text
Surface ProgramNode
  -> one Surface ModuleNode per source module
  -> one existing semantic ModuleNode per compilation unit
```

The Surface AST wire schema is
`frontend/schemas/language_surface_ast.schema.json`. The semantic projection
continues to use `reasonscript-ast/0.1` without an interface version change.

## 3. Design Principles

### 3.1 Immutability

Every node is a frozen value. Parsing, validation, serialization, projection,
and compilation do not mutate the AST.

### 3.2 Source Order

`ProgramNode.modules`, `ModuleNode.body`, calculation statements, conditional
branches, match arms, transition body statements, imports, requirements, and
goal references preserve source order.

### 3.3 One Primary Node

Each recognized syntax construct creates one primary node. Supporting nodes,
such as `ExpressionNode`, `PatternNode`, `ElseIfNode`, `ElseNode`, and
`MatchArmNode`, are owned by that primary node and do not create duplicate
top-level declarations.

## 4. Root and Module Mapping

```text
ProgramNode {
  modules: tuple<ModuleNode>
}

ModuleNode {
  name: Identifier
  visibility: Public | Private
  body: tuple<AstNode>
}
```

```text
pub module finance { ... } -> visibility Public
module finance { ... }     -> visibility Private
```

Validation:

- M-001: module name is required and is a valid identifier.
- M-002: module names are unique in a Program.

## 5. Import Mapping

```text
import finance.loan
import finance.loan as loan
```

maps to:

```text
ImportNode {
  path: ("finance", "loan")
  alias: None | "loan"
}
```

I-001 rejects an empty path. Every path segment and alias is an Identifier.

## 6. Declaration Mapping

| Surface | Primary node | Required field |
|---|---|---|
| `concept Person` | `ConceptNode` | `name` |
| `object User` | `ObjectNode` | `name` |
| `event Login` | `EventNode` | `name` |
| `action Approve` | `ActionNode` | `name` |
| `attribute Age` | `AttributeNode` | `name` |
| `goal LoanApproval` | `GoalNode` | `name` |
| `constraint Adult` | `ConstraintNode` | `name` |

Declaration names share one module namespace and MUST be unique.

## 7. Relation Mapping

```text
User IsA Person
```

maps to:

```text
RelationNode {
  source: "User"
  relation: IsA
  target: "Person"
}
```

Supported relations are `IsA`, `PartOf`, `Cause`, `Dependency`,
`Constraint`, `Temporal`, `Spatial`, and `Similar`.

R-001, R-002, and R-003 require a valid source, target, and relation.
AST-V004 requires source and target declarations to resolve in the module.

## 8. Transition Mapping

```text
transition Approve {
  Draft -> Approved
  requires Adult
  goal LoanApproval
}
```

maps to:

```text
TransitionNode {
  name: "Approve"
  from_state: "Draft"
  to_state: "Approved"
  requirements: ("Adult")
  goals: ("LoanApproval")
  body: ()
}
```

T-001 through T-003 require the name and both endpoint identities.
Constraint and Goal references MUST resolve to declarations of the matching
kind. Endpoint identities are domain State identities and are not required to
be module declarations, preserving `reasonscript-language/0.1`.

## 9. Calculation and Variable Mapping

```text
calculation RiskScore goal:value {
  let income = 100
  result = income * factor
}
```

maps to:

```text
CalculationNode {
  name: "RiskScore"
  goal_annotation: "value"
  body: (LetNode(...))
  result: ExpressionNode("income * factor")
}
```

The sole `result` assignment is stored in the dedicated `result` field and is
not duplicated in `body`.

Validation:

- C-001: calculation name required.
- C-002: result expression required.
- C-003: exactly one result assignment.
- L-001: Let identifier required.
- L-002: Let expression required.

## 10. Conditional Mapping

`if`, ordered `elif`, and optional `else` map to one `IfNode`:

```text
IfNode {
  condition: ExpressionNode
  body: tuple<AstNode>
  elif_branches: tuple<ElseIfNode>
  else_branch: ElseNode | None
}
```

Nested statement order is retained inside each branch.

## 11. Match Mapping

```text
match state {
  Draft => approve()
  _ => reject()
}
```

maps to one `MatchNode` with ordered `MatchArmNode` values. Each arm contains
one `PatternNode` and an ordered body.

MT-001 requires an expression. MT-002 requires at least one arm. AST-V007
requires every arm pattern to be non-empty.

## 12. AST Validation

The Phase 1.1 validator enforces:

| Rule | Meaning |
|---|---|
| AST-V001 | Every object is a known node type and the root is ProgramNode |
| AST-V002 | Identifiers are non-empty and match `[A-Za-z_][A-Za-z0-9_]*` |
| AST-V003 | Module names and declaration symbols are unique |
| AST-V004 | Relation, Constraint, and Goal references resolve |
| AST-V005 | Calculation has one dedicated Result expression |
| AST-V006 | Transition name and endpoint identities are present |
| AST-V007 | Match expression, arms, and patterns are valid |

Validation fails before semantic AST projection or compiler invocation.

## 13. Serialization

`to_json_value` emits implementation-neutral JSON with an explicit
`node_type` discriminator on every node. `from_json_value` reconstructs the
immutable AST.

The JSON Schema fixes:

- Program and Module structure;
- all node type discriminators;
- required fields;
- visibility and relation enums;
- recursive statement, branch, and match-arm shapes.

For every valid Phase 1.1 AST:

```text
from_json_value(to_json_value(ast)) == ast
```

## 14. Semantic AST Projection

Each Surface Module projects to one existing semantic Module:

- imports preserve path order and become semantic module import strings;
- one semantic initial State stores module name, visibility, and declaration
  inventory;
- the first surface Goal becomes the semantic `reach_state` target;
- if no surface Goal exists, `<ModuleName>Result` is synthesized;
- Constraint declarations become semantic Constraint nodes;
- Relation declarations become semantic Transition nodes;
- Transition declarations preserve names and endpoints;
- Calculation statements and Result expressions become explicit semantic
  Transition nodes;
- surface version is emitted as Metadata.

Concept, Object, Event, Action, and Attribute declarations remain represented
in the initial State declaration inventory. This avoids creating multiple
initial semantic State nodes, which `reasonscript-ast/0.1` forbids.

## 15. Compiler Integration

The projected semantic Module passes through the existing compiler unchanged:

```text
Surface AST
  -> project_module
  -> reasonscript-ast/0.1 ModuleNode
  -> frontend.compiler.compile
  -> reason-ir/0.1
```

Phase 1.1 also constructs a schema-valid validation ExecutionPlan by listing
the generated Reason IR transitions in declaration order. This validates
artifact compatibility only; planner selection and Runtime execution meaning
remain outside this mapping specification.

## 16. Conformance

Implementation:

- `frontend/language_surface/lexer.py`
- `frontend/language_surface/nodes.py`
- `frontend/language_surface/parser.py`
- `frontend/language_surface/validation.py`
- `frontend/language_surface/integration.py`
- `frontend/schemas/language_surface_ast.schema.json`

Validation suite:

```sh
python3 -m unittest discover \
  -s language_surface_ast_mapping_tests -p 'test_*.py' -v
```

All existing AST, parser, compiler, Reason IR, Operational Semantics,
Calculation Semantics, Computation Model, and HybridRuntime tests remain
mandatory regressions.
