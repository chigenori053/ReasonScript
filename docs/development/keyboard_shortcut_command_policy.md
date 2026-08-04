# Keyboard Shortcut Command Policy

Specification: `reasonscript-ide/command-settings-notification-adapter/phase-4-c`

Shortcuts bind to `IdeCommand` names, not directly to UI handlers. This keeps
browser keydown handling, future desktop menus, and OS-specific accelerators on
the same command surface.

Initial bindings:

```txt
saveFile      mac Cmd+S          windows Ctrl+S          linux Ctrl+S
analyzeFile   mac Cmd+Enter      windows Ctrl+Enter      linux Ctrl+Enter
showProblems  mac Cmd+Shift+M    windows Ctrl+Shift+M    linux Ctrl+Shift+M
```

The binding table is defined in the UI platform layer. Full OS-level shortcut
binding is outside Phase 4-C.
