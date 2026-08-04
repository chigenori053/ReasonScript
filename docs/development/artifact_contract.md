# ReasonScript — Artifact Path Contract

## Standard Artifacts

The following runtime artifacts are produced by the ReasonScript compiler and runtime:

| File                | Content                              |
|---------------------|--------------------------------------|
| `ast.json`          | Parsed Abstract Syntax Tree          |
| `semantic_ast.json` | Semantically annotated AST           |
| `reason_ir.json`    | Reason Intermediate Representation   |
| `execution_plan.json` | Execution plan                     |
| `simulation.json`   | Simulation trace                     |
| `knowledge.json`    | Knowledge graph output               |
| `diagnostics.json`  | Compiler / runtime diagnostics       |
| `validation.json`   | Validation results                   |

## Output Path

The standard artifact output root is:

```
.reasonscript/artifacts/
```

This directory is relative to the workspace root (the directory the user opened in the IDE).

### Per-Module Layout

When artifacts are managed per source file:

```
.reasonscript/artifacts/<module-name>/ast.json
.reasonscript/artifacts/<module-name>/reason_ir.json
...
```

The `<module-name>` corresponds to the source file stem (e.g., `main` for `main.rsn`).

## Version Field

Every artifact JSON must include a top-level `version` field:

```json
{
  "version": "0.5",
  ...
}
```

This allows the IDE to detect format changes and display upgrade notices.

## Fallback Policy

- **ART-004**: A missing artifact is not a fatal error. The IDE continues to function with available artifacts.
- **ART-005**: The IDE provides a raw JSON fallback view for any artifact, regardless of schema version.
- **ART-006**: A JSON parse error in an artifact is displayed as a diagnostic message in the IDE, not a crash.

## IDE Behavior on Artifact Load

| Condition              | IDE Response                                  |
|------------------------|-----------------------------------------------|
| File missing           | Show placeholder / "not yet compiled" message |
| JSON parse error       | Show diagnostics panel with error detail      |
| Version mismatch       | Show version warning, attempt best-effort display |
| All artifacts present  | Normal visualization                          |

## `.reasonscript/` Directory

The `.reasonscript/` directory at workspace root is created automatically on first compile.  
It should be added to `.gitignore` for user projects (it contains build outputs).

```gitignore
.reasonscript/
```
