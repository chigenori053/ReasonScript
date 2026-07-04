# Sample Selector Final Decision Phase 4.5-C2-E

## Status

IMPLEMENTED for Phase 4.5-C2-E.

## Decision

Sample selector is reclassified from `DEFERRED` to `MIGRATED`.

Official IDE feature name:

- Sample Browser / Example Loader

## Placement

The migration preserves the Standard Layout top-level tabs:

- Right Inspector: `Overview`, `Plan`, `Simulation`, `Knowledge`, `Artifacts`
- Bottom Tool Window: `Problems`, `Output`, `Logs`, `Tests`

Sample Browser placement:

- Workspace Explorer: Examples section with sample list, category, title, and
  description.
- Editor: explicit Open Example action loads selected sample source.
- Problems: sample load errors, fetch failures, missing source failures, and
  dirty-editor blocked loads.
- Output: sample load logs and `/api/examples` fetch logs.
- Artifacts: selected sample metadata and raw sample metadata.

No new top-level right inspector tab is added.

## API Policy

The official IDE calls the existing endpoint:

- `GET /api/examples`

The migration does not remove endpoints and does not change backend request or
response schemas. It is implemented without backend contract rewrite. Client
code tolerates missing examples result, malformed optional examples sections,
and missing metadata by preserving raw sample data and rendering fallback
empty states.

## Sample Load Safety Policy

- Failed sample load must not mutate editor source.
- Missing source must not mutate editor source.
- Unsaved editor content must not be silently overwritten.
- Sample load result must be logged.
- Sample load failure must be visible in Problems.
- Loaded sample source is treated separately from a selected workspace file.
- Saving loaded sample source as a workspace file requires an explicit future
  save action.

Fallback empty states:

- No examples available.
- No sample selected.
- Sample source unavailable.
- Example loading failed.
- Examples unavailable.

## View Model

`apps/reasonscript-ide/ui/src/viewModels/sampleBrowser.ts` provides the
normalized sample model:

- `SampleBrowserStatus`
- `SampleLoadStatus`
- `ReasonScriptSample`
- `SampleLoadIssue`
- `SampleOperationLog`
- `SampleBrowserViewModel`

`buildSampleBrowserViewModel` accepts unknown `/api/examples` data, tolerates
missing examples, preserves raw metadata, normalizes id/title/source fields,
computes category count deterministically, returns unavailable or empty status
when no examples are present, and does not fabricate source code.

## Deletion Gate Impact

All legacy UI migration and decision blockers have been resolved. Physical
deletion of `playground/frontend` remains out of scope until Phase 4.5-D
physical removal planning and deletion-after-removal validation.

Current deletion gate:

ALL LEGACY FEATURE DECISIONS RESOLVED - READY FOR PHYSICAL REMOVAL PLANNING.
