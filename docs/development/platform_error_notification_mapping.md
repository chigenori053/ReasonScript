# Platform Error Notification Mapping

Specification: `reasonscript-ide/command-settings-notification-adapter/phase-4-c`

`PlatformError` values map to notification severity by kind:

| PlatformErrorKind | Notification |
| --- | --- |
| `missing` | warning |
| `read_only` | warning |
| `permission_denied` | error |
| `invalid_encoding` | error |
| `path_traversal` | error |
| `conflict` | warning |
| `unsupported` | warning |
| `network_error` | error |
| `unknown` | error |

The user-facing message remains separate from the machine-readable kind. The
operation and relative path are passed as notification metadata when available.
