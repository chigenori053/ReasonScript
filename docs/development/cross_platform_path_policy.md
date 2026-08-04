# Cross-platform Path Policy

ReasonScript IDE UI state uses slash-normalized relative paths as logical file identities.

Allowed examples:

- `examples/basic.rsn`
- `src/model/main.rsn`

Disallowed in UI state:

- `examples\basic.rsn`
- `/absolute/path/to/basic.rsn`
- `../outside.rsn`
- `C:\project\examples\basic.rsn`

Requirements:

- Store `relative_path` values as slash-normalized relative paths.
- Do not embed OS-specific path separators in UI logic.
- Do not use absolute paths as primary UI identity.
- Reject path traversal patterns through the normalized path validator.

The Phase 4-A validator lives in `apps/reasonscript-ide/ui/src/platform/types.ts` as `isNormalizedRelativePath()` and `validateNormalizedRelativePath()`.
