# AST Schema Validation Specification v0.1

Status: Implemented Draft  
AST ABI: `reasonscript-ast/0.1`  
Serialization: UTF-8 JSON  
Lowering target: `reason-ir/0.1`

## Purpose

The AST ABI is the language-neutral contract shared by ReasonScript parsers,
compilers, language servers, formatters, lint tools, and SDK tooling.

```text
ReasonScript Source -> AST ABI -> AST DTO -> Reason IR
```

Concrete syntax, parser implementation, compiler optimization, and Runtime
execution are outside Phase 1.

## Root Document

The root is a `ModuleNode` with:

- `node_type`: fixed to `ModuleNode`
- `version`: fixed to `reasonscript-ast/0.1`
- `node_id`: non-empty document-unique ID
- `imports`: optional language-neutral module references
- `declarations`: non-empty semantic node array
- `metadata`: optional metadata node array

`node_type` is the required discriminator for heterogeneous JSON node arrays.
It is semantic ABI metadata, not concrete source syntax.

## Node Schemas

| Node | Required fields |
|---|---|
| `GoalNode` | `node_type`, `node_id`, `kind`, `target` |
| `StateNode` | `node_type`, `node_id`, `state_id`, `state_type`, `data` |
| `TransitionNode` | `node_type`, `node_id`, `transition_id`, `source`, `relation`, `target` |
| `ConstraintNode` | `node_type`, `node_id`, `constraint_id`, `kind`, `expression` |
| `ContextNode` | `node_type`, `node_id`, `context_id`, `context_type`, `uri` |
| `MetadataNode` | `node_type`, `node_id`, `key`, `value` |

Transition `expected_cost` defaults to `1.0`, must be finite, and must be
non-negative. Context URIs must be absolute. State data, transition effects,
and metadata values may contain arbitrary JSON with finite numbers.

The normative entry point is `frontend/schemas/ast.schema.json`. Component
schemas are split by node kind in the same directory.

## Semantic Validation

Schema validation is followed by these document-level rules:

1. The root is `ModuleNode` at the supported explicit ABI version.
2. Every `node_id` is non-empty and unique across the module.
3. Exactly one `GoalNode` exists.
4. Exactly one initial `StateNode` exists.
5. Transition, constraint, and context IDs are unique by kind.
6. Context URIs are absolute.
7. JSON payloads contain only JSON-compatible values and finite numbers.
8. Runtime objects, callbacks, pointers, and SDK implementation objects are
   prohibited.
9. Every accepted document lowers deterministically to valid Reason IR 0.1.

The reference validator is available as:

```sh
python3 -m frontend.ast_validator <document.json>
```

## DTO Bindings

Bindings are provided under `frontend/dto/` for Rust, Python, TypeScript, Go,
and Java. They use the same snake_case JSON field names and `node_type`
discriminator.

- Python uses frozen dataclasses.
- TypeScript uses readonly interfaces and a discriminated union.
- Rust uses Serde DTOs and a tagged enum.
- Java uses records, sealed interfaces, and copied immutable lists.
- Go uses value structs and `json.RawMessage` for arbitrary JSON.

DTO round-trip equality is evaluated as JSON value equality. Numerically
equivalent JSON forms such as `1` and `1.0` are equal.

## Fixtures

Valid fixtures:

- `basic_inference.json`
- `constraint.json`
- `context_reference.json`
- `tool_integration.json`
- `worldmodel_transition.json`
- `dbm_planning.json`

Invalid fixtures:

- `duplicate_node_id.json`
- `missing_goal.json`
- `missing_initial_state.json`
- `invalid_uri.json`
- `negative_cost.json`
- `invalid_version.json`

## Conformance Layers

| Layer | Evidence |
|---:|---|
| 0 | Schema and semantic fixture validation |
| 1 | DTO round-trip, immutability/type checks, binding compilation |
| 2 | Deterministic AST lowering |
| 3 | Cross-language AST JSON compatibility |
| 4 | AST to Reason IR mapping and execution compatibility |

Run all layers with:

```sh
python3 frontend/conformance/run_conformance.py
```

Machine-readable results are written to
`frontend/conformance/reports/ast_conformance_results_v0.1.json`.

## Phase 1 Decision

`reasonscript-ast/0.1` is the formal frontend intermediate ABI. The schema,
semantic validator, fixtures, DTO declarations, and conformance framework are
the compatibility boundary for Phase 2 parser validation.
