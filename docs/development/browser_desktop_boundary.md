# Browser / Desktop Boundary

Status: Phase 4-D DRAFT FOR ADOPTION

`BrowserPlatformAdapter` is the official Phase 4 runtime target. It preserves
the Playground-first workflow and uses backend-mediated workspace APIs.

Browser policy:

- Workspace access goes through `/api/workspace/list`, `/api/workspace/read`,
  and `/api/workspace/save` inside `BrowserPlatformAdapter`.
- Artifact access is analyze-result backed through `ArtifactAdapter`.
- Settings use `localStorage` with a memory fallback.
- Notifications may use console fallback.
- Native file dialogs, native menus, and local process execution are not
  exposed.

`DesktopPlatformAdapter` is only a future replacement point for macOS, Windows,
and Linux shell integration. In Phase 4-D it is a stub.

Desktop stub policy:

- It must not imply that a desktop shell exists.
- Native file dialogs are not implemented.
- Native menus are not implemented.
- Local process execution is not implemented.
- Workspace and artifact operations return `PlatformErrorKind` `unsupported`
  until a desktop shell provides real implementations.
- Desktop native notifications are deferred.

The desktop shell phase may later replace these stubs with Tauri or another
native shell implementation without changing the UI-facing `PlatformAdapter`
contract.
