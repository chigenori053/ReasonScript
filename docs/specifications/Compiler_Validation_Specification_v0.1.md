# Compiler Validation Specification v0.1

Status: Implemented Draft
Compiler contract: `compiler/0.1`
Input ABI: `reasonscript-ast/0.1`
Output ABI: `reason-ir/0.1`

## Purpose

The compiler is the deterministic, meaning-preserving boundary from the
versioned semantic AST to Reason IR.

```text
AST ABI
  -> AST Validator
  -> Default Expander
  -> Policy Injector
  -> Reason IR Builder
  -> Reason IR
```

The compiler does not parse source, execute plans, process transactions,
generate machine code, or call the Runtime.

## Compiler Contract

The primary API is:

```python
compile(ast: ModuleNode, policies: CompilationPolicies | None = None) -> dict
```

For JSON-facing tools:

```python
compile_document(ast_json, policies=None) -> dict
```

Successful compilation returns a `reason-ir/0.1` JSON value. Failure raises a
structured `CompilerError`.

## Pipeline

### Stage 1: AST Validation

The compiler requires a `ModuleNode` satisfying both the semantic AST
invariants and `frontend/schemas/ast.schema.json`. Unknown node types are
rejected before lowering.

### Stage 2: Default Expansion

The compiler returns a new immutable canonical AST and never mutates input.
Defaults are:

| Node | Default |
|---|---|
| Goal | `kind = "reach_state"` |
| State | `state_type = "symbolic"`, `data = {}` |
| Transition | `expected_cost = 1.0` |
| Constraint | `kind = "predicate"` |

AST ABI 0.1 requires Goal, State, and Constraint semantic fields. Therefore
parsers and DTO constructors materialize those defaults before compiler input.
`TransitionNode.expected_cost` is optional in JSON and is materialized by the
AST DTO/default expansion path. JSON Schema `default` annotations alone do not
modify input documents.

### Stage 3: Policy Injection

Default execution policy:

```json
{"max_steps": 128, "rollback_on_failure": true, "constraint_mode": "reject"}
```

Default trace policy:

```json
{"level": "standard", "include_alternatives": true, "include_state_data": true}
```

Default planner policy:

```json
{"strategy": "minimum_expected_cost", "max_depth": 128, "max_alternatives": 8}
```

Callers may provide a complete policy override. Partial or unknown fields,
invalid scalar types, negative planner limits, and non-positive `max_steps`
are rejected. Planner policy may explicitly be `null`.

### Stage 4: Reason IR Lowering

| AST | Reason IR |
|---|---|
| `GoalNode` | `goal: GoalSpec` |
| `StateNode` | `initial_state: StateSnapshot` |
| `TransitionNode[]` | `transitions: TransitionSpec[]` |
| `ConstraintNode[]` | `constraints: ConstraintSpec[]` |
| `ContextNode[]` | `context_refs: ContextRef[]` |
| `MetadataNode[]` | `metadata` |

Declaration order is preserved. State data, transition guard/effect,
constraint expression, context URI, and metadata JSON are copied without
semantic rewriting. AST-only node IDs and imports are not Reason IR fields and
are not emitted.

## Error Model

`CompilerError` contains:

```text
code
node_id
message
severity
```

All Phase 3 errors use severity `error`.

| Code | Meaning |
|---|---|
| `compiler.invalid_ast` | Input is not a valid semantic `ModuleNode` |
| `compiler.schema_violation` | AST JSON violates the AST ABI schema |
| `compiler.lowering_failure` | Generated output violates Reason IR requirements |
| `compiler.unsupported_node` | Declaration node type is not supported |
| `compiler.invalid_policy` | Injected policy is incomplete or invalid |

## Compiler Invariants

1. Every successful compilation produces schema-valid Reason IR 0.1.
2. Repeated compilation of the same AST and policies is equal.
3. Initial state identity, type, and data are preserved.
4. Transition IDs, endpoints, relations, costs, guards, effects, and order are
   preserved.
5. Constraint IDs, kinds, expressions, and order are preserved.
6. Context references and metadata are preserved.
7. The compiler package contains no Runtime execution dependency.

## Fixtures

`frontend/compiler_fixtures/valid/` contains six AST inputs:

- `basic_inference.ast.json`
- `constraint.ast.json`
- `context_reference.ast.json`
- `tool_integration.ast.json`
- `worldmodel_transition.ast.json`
- `dbm_planning.ast.json`

`frontend/compiler_fixtures/expected/` contains the corresponding fixed
`*.ir.json` outputs.

Invalid fixtures cover version mismatch, duplicate node IDs, invalid
transition, invalid constraint, invalid context, and unsupported node type.

## Conformance Layers

| Layer | Validation |
|---:|---|
| 0 | AST schema/invariant validation and compiler errors |
| 1 | Default materialization and immutable expansion |
| 2 | Default/custom policy injection and invalid policy rejection |
| 3 | Exact expected Reason IR and semantic preservation |
| 4 | Reason IR schema/semantic compatibility and Runtime independence |
| 5 | AST/compiler/reference Runtime result and Source-to-Runtime chain |

Run all layers with:

```sh
python3 frontend/compiler_conformance/run_conformance.py
```

Compile one AST document with:

```sh
python3 -m frontend.compiler module.ast.json
```

## Phase 3 Decision

`compiler/0.1` formally owns AST validation, canonical default expansion,
policy injection, and Reason IR construction. Future optimization stages must
operate outside this semantic lowering contract or prove equivalent output.
