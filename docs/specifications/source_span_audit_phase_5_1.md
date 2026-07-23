# SourceSpan Audit — Phase 5.1

Generated: Phase 5.1 implementation audit
Status: Initial

## Conventions

- **line/column base**: SourceSpan uses **1-based** line and column numbers throughout the IDE UI layer. `compiler_bridge.rs` converts 0-based pipeline errors (`line - 1`) before storing in `PlatformDiagnostic.span`.
- **uri**: Always present when span is present. Matches `SourceFileState.uri` in ProjectState.

---

## Audit Results

| Artifact type | Span available | Source | Notes | Phase 5.1 action |
|---|---|---|---|---|
| `ProjectState.diagnostics[].span` | Partial | `compiler_bridge.rs` / pipeline | Present when pipeline returns `line`. Null for normalized pipeline errors. | Use span when available; fallback to no-op. |
| `ProjectState.surface_ast` nodes | Not attached | `frontend/language_surface/parser.py` | Parser does not propagate span into JSON artifact yet. | Deferred — fallback only. |
| `ProjectState.semantic_ast` nodes | Not attached | `frontend/language_surface/integration.py` | No span propagation in semantic pass. | Deferred. |
| `ProjectState.reason_ir.transitions[].span` | Missing | `frontend/language_surface/` compiler | Reason IR JSON has no `span` field on transitions. | Use `effect.function` name as symbol fallback. |
| `ProjectState.reason_ir.transitions[].effect.span` | Missing | compiler | No span on effect nodes. | Use `effect.function` / `return_path` as fallback label. |
| `ProjectState.execution_plan.selected_steps[].span` | Missing | `playground/backend/engine.py` | Steps have `transition_id` but no span. | Resolve via `transition_id` → Reason IR transition → symbol fallback. |
| `ProjectState.execution_plan.selected_steps[].transition_id` | **Present** | engine | Key linkage field available. | Use to resolve Reason IR transition. |
| `ProjectState.validation` items | Partial | `playground/backend/main.py` | Validation report has `errors[]` matching diagnostics. | Cross-reference with `ProjectState.diagnostics`. |
| Dependency graph nodes | Absent from ProjectState | analyzer | `ProjectState.analyzer` is null currently. | Read from `ProjectState.analyzer` if present; no-op otherwise. |

---

## Phase 5.1 Minimum Span Targets

The following are required for Phase 5.1 acceptance:

```
Diagnostics  → span (when pipeline provides line number)
Reason IR transition → symbol fallback (effect.function name)
ExecutionPlan step  → transition_id → Reason IR transition → symbol fallback
Validation item     → cross-reference with diagnostics[].span
Dependency node     → no-op if ProjectState.analyzer is null
```

## Fallback Navigation Priority

```
1. artifact.span                    → revealSourceSpan (exact)
2. symbol name (function/transition) → text search in source (best-effort)
3. none                              → no navigation; show "No source span"
```

## 0-based vs 1-based Clarification

- Python pipeline errors: `line` field is **1-based** (from parser).
- `compiler_bridge.rs` stores `start_line = line - 1` (converts to 0-based for internal DTO).
- `sourceNavigation.ts` receives DTO span and adds **+1** before passing to Monaco (Monaco is 1-based).
- Net effect: pipeline line N → DTO start_line N-1 → Monaco line N. ✓
