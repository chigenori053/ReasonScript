# Platform Adapter Contract

`PlatformAdapter` is the UI-facing entry point for platform behavior:

```ts
export interface PlatformAdapter {
  environment: PlatformEnvironment
  workspace: WorkspaceAdapter
  artifacts: ArtifactAdapter
  commands: CommandAdapter
  settings: SettingsAdapter
  notifications: NotificationAdapter
}
```

`PlatformEnvironment` exposes stable capability flags for browser and desktop implementations. Browser defaults disable local filesystem, native dialogs, native menus, and process execution. The Phase 4-D desktop adapter remains a stub and uses conservative capability flags until a shell implementation exists. Unsupported operations still return an explicit `unsupported` error.

Sub-adapter contracts:

- `WorkspaceAdapter` lists, reads, and saves workspace files.
- `ArtifactAdapter` lists and reads artifacts.
- `CommandAdapter` accepts command names such as `saveFile`, `analyzeFile`, and `showOutput`.
- `SettingsAdapter` provides asynchronous get/set storage.
- `NotificationAdapter` exposes info, warning, and error notifications.

Unsupported operations must return `PlatformErrorKind` value `unsupported`, not `unknown`. User-facing messages stay separate from machine-readable error kinds.

The active adapter is resolved with:

```ts
getPlatformAdapter()
```

Phase 4-D defaults to the browser adapter. Tauri or native desktop detection is deferred.
