# ReasonScript IDE Standard Layout

Status: Phase 3.5 DRAFT FOR ADOPTION

ReasonScript IDE uses a five-region layout:

1. Top Bar
2. Left Project Pane
3. Center Editor
4. Right Inspector
5. Bottom Tool Window

The Center Editor remains the primary source editing surface. Runtime
inspection is placed in the Right Inspector, while diagnostics, output, logs,
and test-oriented results are placed in the Bottom Tool Window.

## Top Bar

Required items:

- Project or workspace name
- Selected file
- Compiler mode
- Validate, Run, Analyze, and Audit actions
- Pipeline status
- Dirty state indicator

The Top Bar must not display detailed diagnostics or raw JSON.

## Left Project Pane

The primary left-pane view is Project Explorer. It owns workspace navigation
and selected-file visibility. Runtime metrics and execution results do not
belong in the left pane.

## Center Editor

The Center Editor is the source editing area. It must preserve temporary-source
mode and file-backed workspace editing behavior, including dirty, stale,
missing, and read-only state when available.

## Right Inspector

The Right Inspector has exactly five primary tabs:

- Overview
- Plan
- Simulation
- Knowledge
- Artifacts

## Bottom Tool Window

The Bottom Tool Window has exactly four primary tabs:

- Problems
- Output
- Logs
- Tests

This layout is a UI information architecture change only. Parser, runtime,
artifact, workspace, and `/api/analyze` contracts remain unchanged.
