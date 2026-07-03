# Settings Adapter Contract

Specification: `reasonscript-ide/command-settings-notification-adapter/phase-4-c`

`SettingsAdapter` provides small IDE preference persistence behind the
`PlatformAdapter` boundary.

## Interface

```ts
get<T>(key: string): Promise<T | null>
set<T>(key: string, value: T): Promise<void>
remove?(key: string): Promise<void>
```

## Keys

```txt
compilerMode
rightInspector.activeTab
bottomToolWindow.activeTab
bottomToolWindow.visible
layout.leftPaneWidth
layout.rightPaneWidth
layout.bottomPaneHeight
workspace.lastRoot
```

## Browser Policy

Browser settings use `localStorage` with the `reasonscript.ide.` prefix. If
`localStorage` is unavailable, rejects writes, or contains invalid JSON, the
adapter falls back to in-memory storage and must not crash the UI.
