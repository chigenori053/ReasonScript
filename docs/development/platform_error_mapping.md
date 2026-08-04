# Platform Error Mapping

Status: Phase 4-B DRAFT FOR ADOPTION

`PlatformError` separates user-facing messages from machine-readable failure
kinds. Browser workspace and artifact adapters map backend, validation, HTTP,
and fetch failures into `PlatformErrorKind`.

Workspace backend mappings:

| Backend code | PlatformErrorKind |
| --- | --- |
| `NOT_FOUND` | `missing` |
| `PATH_TRAVERSAL` | `path_traversal` |
| `PERMISSION_DENIED` | `permission_denied` |
| `DECODE_ERROR` / `INVALID_ENCODING` | `invalid_encoding` |
| `VERSION_CONFLICT` | `conflict` |
| `READ_ONLY` | `read_only` |

HTTP mappings:

| HTTP status | PlatformErrorKind |
| --- | --- |
| `404` | `missing` |
| `409` | `conflict` |
| other non-2xx | `network_error` |

Thrown fetch failures are returned as `network_error`. Unsupported desktop stub
operations return `unsupported`.
