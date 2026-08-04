# Phase 4 Cross-platform Foundation

Status: Phase 4-D DRAFT FOR ADOPTION

ReasonScript IDE Phase 4 fixes the browser-first cross-platform adapter
foundation. The UI talks to platform services through one boundary:

```txt
UI Components
  -> CommandRegistry / UI State
  -> PlatformAdapter
      -> WorkspaceAdapter
      -> ArtifactAdapter
      -> CommandAdapter
      -> SettingsAdapter
      -> NotificationAdapter
  -> BrowserPlatformAdapter or DesktopPlatformAdapter
```

Phase 4-A introduced the adapter core, environment flags, platform errors, and
normalized relative path validation. Phase 4-B moved workspace and artifact
access behind the adapter boundary. Phase 4-C moved IDE actions, persistent UI
settings, shortcut binding policy, and user notifications behind command,
settings, and notification adapters.

Phase 4-D does not add desktop features. It consolidates the policies, adds
integration tests for the complete Phase 4 boundary, and documents that the
current official runtime remains the browser Playground-first IDE.

Final Phase 4 policy:

- UI components do not directly implement browser or desktop differences.
- Browser-specific behavior lives in `BrowserPlatformAdapter`.
- Desktop-specific behavior is deferred to a later desktop shell phase.
- Workspace list/read/save operations use `PlatformAdapter.workspace`.
- Artifact listing and reads use `PlatformAdapter.artifacts`.
- IDE actions use `IdeCommand` through `CommandRegistry`.
- Required UI settings are persisted through `SettingsAdapter`.
- User-visible messages use `NotificationAdapter`.
- UI file identity uses slash-normalized `NormalizedRelativePath`.
- Backend contracts for `/api/analyze` and `/api/workspace/*` are unchanged.

Validation for Phase 4-D is anchored by focused tests under `tests/ide` and the
standard IDE, smoke, backend, frontend build, and `git diff --check` commands.
