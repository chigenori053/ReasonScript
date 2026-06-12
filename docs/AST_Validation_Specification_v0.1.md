# AST Validation Specification v0.1

Status: Implemented Draft  
AST version: `reasonscript-ast/0.1`  
Lowering target: `reason-ir/0.1`

## Purpose

The ReasonScript AST is a language-neutral semantic representation between
source syntax and Reason IR. It represents goals, initial state, transitions,
constraints, context references, and metadata without importing Runtime or SDK
types.

```text
ReasonScript Source -> Semantic AST -> Reason IR
```

Parser implementation, concrete syntax, compiler orchestration, and Runtime
execution are outside Phase 0.

## Hierarchy

```text
ModuleNode
|- GoalNode
|- StateNode
|- TransitionNode
|- ConstraintNode
|- ContextNode
`- MetadataNode
```

Every node has a non-empty, module-unique `node_id`. Semantic identifiers
(`state_id`, `transition_id`, `constraint_id`, and `context_id`) remain
separate because they are emitted to Reason IR.

`ModuleNode` contains:

- `version`: fixed to `reasonscript-ast/0.1`
- `imports`: language-neutral module references
- `declarations`: semantic declarations
- `metadata`: key/value metadata declarations

Exactly one `GoalNode` and exactly one initial `StateNode` are required. Reason
IR 0.1 stores one initial snapshot; intermediate and target states are named by
`TransitionNode.source` and `TransitionNode.target` rather than declared as
additional snapshots.

## Core Nodes

| Node | Required semantic fields |
|---|---|
| `GoalNode` | `kind`, `target` |
| `StateNode` | `state_id`, `state_type`, `data` |
| `TransitionNode` | `transition_id`, `source`, `relation`, `target` |
| `ConstraintNode` | `constraint_id`, `kind`, `expression` |
| `ContextNode` | `context_id`, `context_type`, absolute `uri` |
| `MetadataNode` | `key`, JSON-compatible `value` |

`TransitionNode.expected_cost` defaults to `1.0` because it is required by
Reason IR 0.1. `guard` and `effect` are optional.

## Reason IR Mapping

| AST | Reason IR |
|---|---|
| `GoalNode` | `goal: GoalSpec` |
| `StateNode` | `initial_state: StateSnapshot` |
| `TransitionNode[]` | `transitions: TransitionSpec[]` |
| `ConstraintNode[]` | `constraints: ConstraintSpec[]` |
| `ContextNode[]` | `context_refs: ContextRef[]` |
| `MetadataNode[]` | `metadata` object |

AST-only `node_id`, module version, and imports are not emitted. Execution,
trace, and optional planner policies are compiler lowering options, with
Reason IR-compatible defaults supplied by the reference mapper.

## Validation Rules

1. The root is `ModuleNode` with the supported explicit version.
2. Every AST node ID is non-empty and unique within the module.
3. Exactly one goal and one initial state exist.
4. Reason IR semantic IDs are non-empty and unique by node kind.
5. Transition cost is finite and non-negative.
6. Context URI is absolute.
7. State data, transition effects, and metadata are JSON-compatible and use
   finite numbers.
8. Runtime objects, SDK DTOs, callbacks, and implementation pointers are
   rejected.
9. Every valid module lowers deterministically to schema-valid Reason IR 0.1.

No graph library or graph-first representation is used. Transitions are
state-oriented declarations and are preserved in declaration order.

## Reference Implementation

- `frontend/ast/nodes.py`: immutable core nodes and JSON projection
- `frontend/ast/validation.py`: AST invariants
- `frontend/ast/mapping.py`: deterministic Reason IR lowering
- `ast_validation_tests/`: six validation cases and invariant tests

## Phase 0 Decision

The recommended AST is an immutable semantic module with a flat,
declaration-ordered body. This keeps parser syntax outside the AST, makes the
compiler lowering direct, and preserves State-first Reason IR compatibility.

AST JSON Schema, generated DTO bindings, and cross-language AST conformance
belong to Language Frontend Foundation Phase 1.
