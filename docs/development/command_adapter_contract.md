# Command Adapter Contract

Specification: `reasonscript-ide/command-settings-notification-adapter/phase-4-c`

ReasonScript IDE commands are named operations that can be invoked by top bar
buttons, keyboard shortcuts, future desktop menus, panels, or system actions.

## IdeCommand

The Phase 4-C command surface is:

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

## Request / Result

`CommandAdapter.execute()` accepts a `CommandRequest` with a command, optional
payload, and optional source. It returns a `CommandResult` with `ok`, the command
name, and either a message or a `PlatformError`.

Unsupported commands return `PlatformErrorKind = unsupported`.

## Registry

`CommandRegistry` maps `IdeCommand` values to UI handlers. It is intentionally
small and reusable by top bar actions, shortcuts, panel buttons, and future menu
bindings.
