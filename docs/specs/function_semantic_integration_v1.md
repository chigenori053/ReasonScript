# Function Semantic Integration Specification v1.0

Specification ID: `function-semantic-integration/1.0`

This repository implements `fn` as a first-class language-surface construct across:

- Surface AST: `FunctionDeclarationNode` remains in `ModuleNode.body`.
- Semantic AST artifact: function declarations are projected as `SemanticFunctionNode` metadata and `FunctionSymbol` entries.
- Reason IR artifact: functions are lowered into `metadata.function_ir` as `FunctionIRNode`, and calls into `metadata.function_calls` / transition effects as `FunctionCallIRNode`.
- Dependency analysis: calls from calculations add `function -> calculation` edges.
- Execution: called functions emit `FunctionReturnTransition` evidence before the consuming calculation result transition.
- Knowledge: function-call execution preserves the function return in evidence while extracting the calculation result as knowledge.

## Function Composition

Nested calls are lowered in evaluation order, from the innermost call to the
outermost call. When a branching inner call has multiple return states, those
states converge through unique `FunctionCallMergeTransition` edges before the
outer call is evaluated. `FunctionReturnTransition.transition_id` remains the
canonical `<function>.return[.<path>]` identity and is unique within Reason IR.

Compile-time evaluation of literal nested calls supplies the inner return value
to the outer function's evaluation context. Execution evidence preserves each
selected function return in inner-to-outer order.

## Function Signature Layout

Typed parameter lists may span multiple source lines. Newlines inside the
opening and closing parentheses are treated as whitespace before parameter and
return-type parsing.

Validation coverage:

- `FN-001`: duplicate function symbol.
- `FN-002`: function parameters require declared types.
- `FN-003`: function return type is required.
- `FN-004`: non-void functions require a guaranteed terminal return.
- `FN-005`: return expressions and call arguments must match declared types.
- `FN-006`: duplicate parameter names are invalid.
- `FN-007`: controlled recursion (direct and mutual) is permitted under the deterministic `max_call_depth` runtime limit (Phase 4).
- `FN-008`: nested calls preserve inner-to-outer evaluation order and unique
  transition identities.
- `FN-009`: multiline typed parameter lists parse equivalently to single-line
  parameter lists.
