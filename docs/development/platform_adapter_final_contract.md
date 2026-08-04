# Platform Adapter Final Contract

Status: Phase 4-D DRAFT FOR ADOPTION

Phase 4-D fixes the Phase 4 `PlatformAdapter` contract as the UI-facing
platform boundary:

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

Sub-adapter responsibilities:

- `WorkspaceAdapter`: `listWorkspace`, `readFile`, `saveFile`.
- `ArtifactAdapter`: `getArtifactIndex`, `readArtifact`.
- `CommandAdapter`: execute `IdeCommand` requests.
- `SettingsAdapter`: asynchronous get/set/remove for UI settings.
- `NotificationAdapter`: `info`, `warning`, and `error` user messages.

Required command names:

```txt
openWorkspace
refreshWorkspace
saveFile
analyzeFile
runCurrentFile
validateWorkspace
auditProject
showOverview
showPlan
showSimulation
showKnowledge
showArtifacts
showProblems
showOutput
showLogs
showTests
clearOutput
clearNotifications
```

Required persisted settings:

- `compilerMode`
- `rightInspector.activeTab`
- `bottomToolWindow.activeTab`

Required artifact file names:

- `ast.json`
- `semantic_ast.json`
- `reason_ir.json`
- `execution_plan.json`
- `simulation.json`
- `knowledge.json`
- `diagnostics.json`
- `validation.json`

Unsupported operations return `PlatformErrorKind` `unsupported`, not `unknown`.
Network failures map to `network_error`, path validation failures map to
`path_traversal`, and version conflicts map to `conflict`.
