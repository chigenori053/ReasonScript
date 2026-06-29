# Playground Runtime Integration

ReasonScript IDE Phase 2 treats the Playground IDE as the primary runtime integration surface.

The stabilized flow is:

```text
Source -> Surface AST -> Semantic AST -> Reason IR -> ExecutionPlan -> Simulation -> Knowledge -> Diagnostics
```

The Playground backend exposes this flow through `POST /api/analyze`. The response keeps runtime artifacts, pipeline status, structured view data, and diagnostics in one deterministic payload. Existing compile/run endpoints may remain available, but `/api/analyze` is the Phase 2 contract endpoint.

Required IDE panels:

- Pipeline Overview
- Source Model
- ExecutionPlan
- Simulation Trace
- Knowledge Evidence
- Runtime Operations
- Output
- Diagnostics
- Raw JSON fallback

Missing artifacts must be rendered as empty, skipped, or unavailable states. They must not crash the IDE.
