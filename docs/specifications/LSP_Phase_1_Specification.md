# LSP Phase 1 Specification

Status: Design Complete

Implementation: Deferred

LSP Phase 1 defines the first official ReasonScript language-server scope. It
does not increase runtime capability; it targets developer productivity,
navigation, diagnostics, and maintainability.

## Scope

LSP Phase 1 SHALL support:

- Diagnostics
- Hover
- Completion
- Go To Definition
- Find References
- Symbol Index

## Diagnostics

Diagnostics SHALL expose compiler and platform errors including:

- `TypeMismatch`
- `ModuleNotFound`
- `UnknownReasoningState`
- `ExecutionPlanCompatibilityFailed`

## Hover

Hover SHALL expose symbol information for:

- Goal
- State
- ReasonGraph
- ExecutionPlan
- Function
- Struct
- Enum

## Completion

Completion SHALL provide context-aware suggestions for:

- `runtime.search`
- `runtime.simulate`
- `goal`
- `state`
- `reason_graph`
- `execution_plan`

## Navigation

Go To Definition SHALL support:

- Function
- Struct
- Enum
- Goal
- State
- ReasonGraph
- ExecutionPlan

Find References SHALL support:

- Module
- Function
- Reasoning Types
- Runtime APIs

## Symbol Index

The workspace symbol index SHALL track:

- Modules
- Functions
- Structs
- Enums
- Goals
- States
- ReasonGraphs
- ExecutionPlans
