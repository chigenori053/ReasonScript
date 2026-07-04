# ReasonScript IDE Phase 5 — Official IDE Workspace Completion

## Status

DRAFT FOR ADOPTION

## Summary

Phase 5 completes the official ReasonScript IDE (`apps/reasonscript-ide/ui`)
as a workspace-aware authoring environment, following the removal of the
legacy Playground frontend in Phase 4.5-D.

Phase 5 adds:

- Workspace diagnostics (5.1)
- File-level diagnostic mapping (5.2)
- Workspace / editor state consistency (5.3)
- Stale artifact detection (5.4)
- Project validation summary (5.5)
- Problems / Output / Logs final integration (5.6)
- IDE V0.5 acceptance tests (5.7)

See the per-subphase docs listed below for details on each area.

## Related Docs

- [workspace_diagnostics_phase_5_1.md](workspace_diagnostics_phase_5_1.md)
- [file_level_diagnostics_phase_5_2.md](file_level_diagnostics_phase_5_2.md)
- [workspace_editor_state_phase_5_3.md](workspace_editor_state_phase_5_3.md)
- [stale_artifact_detection_phase_5_4.md](stale_artifact_detection_phase_5_4.md)
- [project_validation_summary_phase_5_5.md](project_validation_summary_phase_5_5.md)
- [problems_output_logs_integration_phase_5_6.md](problems_output_logs_integration_phase_5_6.md)
- [ide_v0_5_acceptance.md](ide_v0_5_acceptance.md)

## Layout Policy

Phase 5 keeps the Standard IDE Layout unchanged. No new top-level right
inspector tab is added; workspace diagnostics, file mapping, editor state,
stale-artifact, and project validation surfaces are all integrated into the
existing Overview / Workspace Explorer / Problems / Output / Logs / Artifacts
surfaces.

## Data Contract

All new view models derive from data already returned by `/api/analyze` and
`/api/workspace/*` (via `ProjectState` and `WorkspaceState`). No backend API
contract is broken and no new backend endpoint is introduced.

## Validation

- `python3 -m pytest tests/ide -q`
- `python3 scripts/dev.py test ide`
- `python3 scripts/dev.py test frontend`
- `cd apps/reasonscript-ide/ui && npm run build`
