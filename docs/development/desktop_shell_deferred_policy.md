# Desktop Shell Deferred Policy

Status: Phase 4-D DRAFT FOR ADOPTION

Desktop shell implementation is outside Phase 4-D.

Deferred items:

- Tauri integration
- Native file dialogs
- Native menu
- OS-level shortcut registration
- Local process execution
- Installer and packaging
- Auto updater
- Terminal emulator
- Desktop native notifications

Phase 4-D only preserves a desktop adapter stub as the future replacement point.
The stub returns `unsupported` for unimplemented operations and uses conservative
capability flags so the UI does not treat desktop shell features as available.

Future desktop work must reuse the Phase 4 `PlatformAdapter` contract instead
of adding direct OS-specific behavior to UI components.
