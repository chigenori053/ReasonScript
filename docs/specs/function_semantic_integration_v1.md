# Function Semantic Integration Specification v1.0

Specification ID: `function-semantic-integration/1.0`

This repository implements `fn` as a first-class language-surface construct across:

- Surface AST: `FunctionDeclarationNode` remains in `ModuleNode.body`.
- Semantic AST artifact: function declarations are projected as `SemanticFunctionNode` metadata and `FunctionSymbol` entries.
- Reason IR artifact: functions are lowered into `metadata.function_ir` as `FunctionIRNode`, and calls into `metadata.function_calls` / transition effects as `FunctionCallIRNode`.
- Dependency analysis: calls from calculations add `function -> calculation` edges.
- Execution: called functions emit `FunctionReturnTransition` evidence before the consuming calculation result transition.
- Knowledge: function-call execution preserves the function return in evidence while extracting the calculation result as knowledge.

Validation coverage:

- `FN-001`: duplicate function symbol.
- `FN-002`: function parameters require declared types.
- `FN-003`: function return type is required.
- `FN-004`: non-void functions require a guaranteed terminal return.
- `FN-005`: return expressions and call arguments must match declared types.
- `FN-006`: duplicate parameter names are invalid.
- `FN-007`: direct recursive calls are rejected for v1.0.

