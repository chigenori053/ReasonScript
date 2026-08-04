# Right Inspector Contract

Status: Phase 3.5 DRAFT FOR ADOPTION

The Right Inspector is limited to runtime reasoning inspection and exposes
exactly five primary tabs.

## Primary Tabs

- Overview: latest analyze/run summary, pipeline status, diagnostics summary,
  output summary, knowledge count, and artifact availability.
- Plan: ExecutionPlan goal, distance, ordered steps, selected branch,
  alternative paths, unreachable reason, and calculation/cycle details when
  available.
- Simulation: execution trace, runtime events, branch selection events, input
  state, output references, and final state.
- Knowledge: generated knowledge items and evidence details, including path
  signature and branch-derived data when available.
- Artifacts: raw JSON and internal artifacts, including AST, Semantic AST,
  Reason IR, ExecutionPlan, Simulation, Knowledge, Diagnostics, and Validation.

## Migration

Diagnostics detail moves to Bottom Problems. Runtime output moves to Bottom
Output. Raw JSON views are grouped under Artifacts. Metrics are no longer
primary tabs; important summaries may appear in Overview.
