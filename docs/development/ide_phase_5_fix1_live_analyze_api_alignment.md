# ReasonScript IDE Phase 5-Fix1 - Live Analyze API Alignment

## Status

VALIDATED

## Observed Error

Live browser/backend validation showed the official IDE Analyze action failing with:

```text
Analyze request failed with status 404 at buildProjectState
```

## Root Cause

The official IDE Analyze path must use the existing backend contract:

```text
POST /api/analyze
```

The backend does not define `/api/build-project-state` or `/api/project-state`, and Phase 5-Fix1 must not introduce a breaking backend API change.

## Selected Fix

`apps/reasonscript-ide/ui/src/bridge.ts` keeps `buildProjectState` as the adapter over `POST /api/analyze`.

The request payload follows `playground/backend/main.py` `SourceRequest`:

```json
{
  "source": "...",
  "filename": "main.rsn",
  "compiler_mode": "normal"
}
```

When workspace context is available, `source_context` is included without changing the backend schema.

## Normalization Policy

`buildProjectState` normalizes the analyze response into `ProjectState` with fallbacks for:

- `schema_version`
- `compiler_version`
- `source_files`
- `diagnostics`
- `artifacts`
- `analyzer`
- `metadata`
- `generated_at`

## Endpoint Policy

Allowed:

- `POST /api/analyze`

Forbidden in `buildProjectState`:

- `/api/build-project-state`
- `/api/project-state`

## Validation Commands

```bash
npm --prefix apps/reasonscript-ide/ui run build
python3 -m pytest tests/ide/test_phase5_fix1_live_analyze_api_alignment.py -v --tb=short
python3 -m pytest tests/ide -q
python3 scripts/dev.py test frontend
python3 scripts/dev.py test ide
git diff --check
```

## Live Validation

Run the backend and IDE UI:

```bash
python3 scripts/dev.py backend
python3 scripts/dev.py ide-ui
```

Then verify that Analyze does not return 404 and that the IDE updates from the analyzed `/api/analyze` response.

Result on 2026-07-05:

- `POST http://127.0.0.1:8000/api/analyze` returned 200.
- `POST http://127.0.0.1:5173/api/analyze` returned 200 through Vite proxy.
- Analyze response included `ok: true`, pipeline stages, and artifacts.

## Phase 6 Status

Phase 5-Fix1 live API validation is complete. Phase 6 remains gated on commit/push policy.
