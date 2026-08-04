# Export / Import / Diff Migration Phase 4.5-C2-C

## Status

IMPLEMENTED for Phase 4.5-C2-C.

## Summary

Phase 4.5-C2-C migrates the legacy artifact workflow into the official IDE
without deleting `playground/frontend` and without rewriting backend API
contracts.

Migrated features:

- Export
- Import
- Diff

## Placement

The migration preserves the Standard Layout top-level tabs:

- Right Inspector: `Overview`, `Plan`, `Simulation`, `Knowledge`, `Artifacts`
- Bottom Tool Window: `Problems`, `Output`, `Logs`, `Tests`

Artifact workflow placement:

- `Artifacts`: export/import/diff operation sections, last operation results,
  raw operation JSON fallback, and empty states.
- `Overview`: artifact workflow summary with export/import/diff status, last
  operation, issue count, and log count.
- `Problems`: normalized import validation errors, export failures, and diff
  compatibility or structural mismatch warnings.
- `Output`: export/import/diff operation logs.

## API Policy

The official IDE calls the existing artifact operation endpoints:

- `POST /api/export`
- `POST /api/import`
- `POST /api/diff`

The migration does not remove endpoints and does not change backend request or
response schemas. Client code tolerates operation failure and malformed
optional sections by preserving raw results and rendering fallback states.

## Import Safety Policy

Import can imply workspace mutation in future phases, so this phase keeps it
validation-first:

- Imported artifacts are displayed and normalized before any editor mutation.
- Failed import does not mutate `selectedFile.content` or editor source.
- Destructive overwrite requires an explicit future confirmation policy.
- Import results report restored artifacts, imported files when available, and
  validation issues in Problems.

## View Model

`apps/reasonscript-ide/ui/src/viewModels/artifactWorkflow.ts` provides the
normalized artifact workflow model:

- `ArtifactOperationKind`
- `ArtifactOperationStatus`
- `ArtifactIssue`
- `ArtifactOperationLog`
- `ExportArtifactResult`
- `ImportArtifactResult`
- `DiffArtifactResult`
- `ArtifactWorkflowViewModel`

`buildArtifactWorkflowViewModel` accepts unknown state, tolerates missing
operation results, preserves raw export/import/diff results, normalizes issues,
and returns idle fallbacks when no operation has run.

## Deletion Gate Impact

Artifact workflow migration is complete, but physical deletion of
`playground/frontend` remains out of scope.

Current deletion gate:

ARTIFACT WORKFLOW MIGRATED - NOT CLOSED.
