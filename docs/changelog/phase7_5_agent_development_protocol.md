# Phase 7.5 Agent Development Protocol

Implemented `reasonscript-agent-protocol/1.0`.

## Changes

- Added repository-level `AGENTS.md` with the canonical agent workflow, validation sequence, artifact policy, golden policy, completion criteria, and report format.
- Added the Phase 7.5 protocol specification under `docs/specifications/`.
- Added CLI support for direct `reason analyze`, `reason artifacts`, `reason validate-artifacts`, and `reason manifest` execution.
- Added `reason agent-protocol` validation for AP-001, AP-002, and AP-003.
- Added `reason agent-report` for deterministic machine-readable task reports.
- Extended protocol validation to AP-001 through AP-010.
- Added canonical `agent_report.json` generation with `version`, task status, test count, artifact status, and required command tracking.
