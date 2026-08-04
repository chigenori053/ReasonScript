# Cross-platform UI Readiness

Status: Phase 3.5 DRAFT FOR ADOPTION

Phase 3.5 does not implement a native desktop shell, but the UI layout must
remain ready for browser and desktop embedding.

## Requirements

- The five-region layout must work inside browser and desktop shells.
- UI logic must not depend on OS-specific path separators.
- `relative_path` values are treated as slash-normalized display paths.
- Keyboard shortcuts should remain command-oriented so desktop menu bindings
  can be added later.
- Right Inspector and Bottom Tool Window should be compatible with future
  resizable panes.
- Native menus, native file dialogs, packaging, and installers are outside
  Phase 3.5.

Backend contracts remain unchanged: `/api/analyze` and workspace list/read/save
request and response shapes are preserved.
