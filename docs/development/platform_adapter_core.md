# Platform Adapter Core

ReasonScript IDE Phase 4-A adds the minimum platform adapter layer needed to keep UI code independent from browser, desktop shell, and OS-specific behavior.

The scope is intentionally small:

- `PlatformAdapter` and `PlatformEnvironment`
- Browser platform adapter
- Desktop platform adapter stub
- Active adapter resolver through `getPlatformAdapter()`
- Basic platform error model
- Slash-normalized relative path type and validator
- Contract tests and documentation

Phase 4-A does not migrate the whole UI to the adapter. Existing Playground-first behavior, `/api/analyze`, `/api/workspace/list`, `/api/workspace/read`, and `/api/workspace/save` contracts remain unchanged.

Desktop shell work is deferred. Native dialogs, native menus, packaging, terminal emulator support, LSP integration, and process execution are outside this phase.

Implementation files:

- `apps/reasonscript-ide/ui/src/platform/types.ts`
- `apps/reasonscript-ide/ui/src/platform/browserAdapter.ts`
- `apps/reasonscript-ide/ui/src/platform/desktopAdapter.ts`
- `apps/reasonscript-ide/ui/src/platform/index.ts`
