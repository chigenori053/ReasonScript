# AST Schema Validation Report v0.1

Status: Passed  
Executed: 2026-06-13

## Deliverables

| Deliverable | Location | Result |
|---|---|---|
| AST JSON Schema | `frontend/schemas/` | Complete |
| AST DTO bindings | `frontend/dto/` | Five languages |
| AST validator | `frontend/ast_validator/` | Complete |
| Valid and invalid fixtures | `frontend/fixtures/` | 6 + 6 |
| AST conformance | `frontend/conformance/` | Five layers |
| Normative specification | `docs/AST_Schema_Validation_Specification_v0.1.md` | Complete |

## Conformance Results

```text
Layer 0 Schema Validation: PASS
Layer 1 DTO Validation: PASS
Layer 2 AST Lowering Validation: PASS
Layer 3 Cross-Language AST Compatibility: PASS
Layer 4 AST -> Reason IR Compatibility: PASS
```

Python, Rust, and TypeScript executed all valid fixture round trips and
produced equivalent JSON values. Java DTO records compiled successfully. The
Go binding is present, but its compile test was skipped because the Go
toolchain is not installed in this environment.

All valid fixtures lower deterministically to schema-valid `reason-ir/0.1`.
The executable inference fixtures reached their expected goals.

## Decision

Phase 1 success and exit criteria are satisfied. `reasonscript-ast/0.1` is
established as the versioned Language Frontend ABI and is ready for Phase 2
Parser Validation.
