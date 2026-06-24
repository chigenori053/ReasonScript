# Playground Function Semantic Audit

Status: implemented for v1.0 acceptance coverage.

| Layer | Coverage |
| --- | --- |
| Parser | `fn` lowers into `FunctionDeclarationNode` in the module body. |
| Surface AST | Function parameters preserve declared types. |
| Semantic AST | `metadata.semantic_functions` contains `SemanticFunctionNode`. |
| Symbol Table | `metadata.function_symbols` contains `FunctionSymbol`. |
| Call Resolution | Calculation calls resolve to module-qualified function names. |
| Reason IR | `metadata.function_ir` and `metadata.function_calls` preserve function evidence. |
| Dependency Graph | Function-to-calculation edges are emitted through `calculation_dependencies`. |
| Execution Plan | Called functions emit `FunctionReturnTransition` before calculation results. |
| Knowledge | Called function evidence is retained in the result knowledge path. |
| Diagnostics | `FN-001` through `FN-007` are structured through validation messages. |

