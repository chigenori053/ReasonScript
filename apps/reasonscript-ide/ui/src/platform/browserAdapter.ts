import type {
  ArtifactAdapter,
  ArtifactDescriptor,
  ArtifactIndexRequest,
  CommandAdapter,
  IdeCommand,
  NotificationAdapter,
  PlatformAdapter,
  PlatformFailure,
  PlatformResult,
  ReadArtifactRequest,
  SettingsAdapter,
  WorkspaceScanStatus,
  WorkspaceAdapter,
  WorkspaceFileNode,
} from "./types";
import {
  createPlatformError,
  unsupportedPlatformError,
  validateNormalizedRelativePath,
} from "./types";

type BackendWorkspaceNode = {
  name: string;
  relative_path?: string;
  path?: string;
  kind?: "file" | "directory" | "symlink" | "unknown";
  extension?: string | null;
  is_directory?: boolean;
  is_source?: boolean;
  is_ignored?: boolean;
  children?: BackendWorkspaceNode[];
};

type BackendError = {
  code?: string;
  message?: string;
};

type BackendResult<T> = ({ ok: true } & T) | { ok: false; error?: BackendError };

function backendErrorToFailure(operation: string, error?: BackendError): PlatformFailure {
  const code = error?.code ?? "UNKNOWN";
  const kind =
    code === "NOT_FOUND"
      ? "missing"
      : code === "PATH_TRAVERSAL"
        ? "path_traversal"
        : code === "PERMISSION_DENIED" || code === "NOT_A_DIRECTORY"
          ? "permission_denied"
          : code === "INVALID_ENCODING" || code === "DECODE_ERROR"
            ? "invalid_encoding"
            : code === "VERSION_CONFLICT"
              ? "conflict"
              : code === "READ_ONLY"
                ? "read_only"
                : "unknown";

  return {
    ok: false,
    error: createPlatformError(kind, error?.message ?? code, { operation }),
  };
}

async function postJson<T>(operation: string, path: string, body: unknown): Promise<PlatformResult<T>> {
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const kind = response.status === 404 ? "missing" : response.status === 409 ? "conflict" : "network_error";
      return {
        ok: false,
        error: createPlatformError(kind, `Request failed with status ${response.status}.`, {
          operation,
        }),
      };
    }

    const data = (await response.json()) as BackendResult<T>;
    if (!data.ok) {
      return backendErrorToFailure(operation, data.error);
    }

    const { ok: _ok, ...payload } = data;
    return { ok: true, ...(payload as T) };
  } catch (cause) {
    return {
      ok: false,
      error: createPlatformError("network_error", "Request failed before a platform response was available.", {
        operation,
        cause,
      }),
    };
  }
}

function mapWorkspaceNode(node: BackendWorkspaceNode): WorkspaceFileNode {
  const relativePath = node.relative_path ?? node.path ?? node.name;
  const pathResult = validateNormalizedRelativePath(relativePath);
  const normalizedPath = pathResult.ok ? pathResult.relativePath : node.name;
  const isDirectory = node.kind === "directory" || node.is_directory === true || Boolean(node.children?.length);

  return {
    name: node.name,
    relativePath: normalizedPath,
    path: normalizedPath,
    relative_path: normalizedPath,
    kind: isDirectory ? "directory" : "file",
    isDirectory,
    isSource: node.is_source,
    isIgnored: node.is_ignored,
    is_ignored: node.is_ignored,
    supported: node.is_ignored ? false : undefined,
    extension: node.extension,
    children: node.children?.map(mapWorkspaceNode),
  };
}

function mapScanStatus(scanStatus: unknown): WorkspaceScanStatus {
  if (!scanStatus || typeof scanStatus !== "object") {
    return { status: "error", truncated: false, maxDepth: 0, maxFiles: 0 };
  }

  const raw = scanStatus as Record<string, unknown>;
  const truncated = Boolean(raw.truncated) || raw.status === "truncated";
  const status = raw.status === "success" && !truncated ? "success" : truncated ? "warning" : "error";

  return {
    status,
    truncated,
    maxDepth: Number(raw.max_depth ?? raw.maxDepth ?? 0),
    maxFiles: Number(raw.max_files ?? raw.maxFiles ?? 0),
    message: typeof raw.message === "string" ? raw.message : undefined,
  };
}

const ARTIFACT_FIELDS: Array<{ name: string; fileName: string; field: string }> = [
  { name: "Surface AST", fileName: "ast.json", field: "surface_ast" },
  { name: "Semantic AST", fileName: "semantic_ast.json", field: "semantic_ast" },
  { name: "Reason IR", fileName: "reason_ir.json", field: "reason_ir" },
  { name: "Execution Plan", fileName: "execution_plan.json", field: "execution_plan" },
  { name: "Simulation", fileName: "simulation.json", field: "simulation" },
  { name: "Knowledge", fileName: "knowledge.json", field: "knowledge" },
  { name: "Diagnostics", fileName: "diagnostics.json", field: "diagnostics" },
  { name: "Validation", fileName: "validation.json", field: "validation" },
];

let analyzeArtifactSource: Record<string, unknown> | null = null;

export function setBrowserAnalyzeArtifactSource(source: unknown): void {
  analyzeArtifactSource = source && typeof source === "object" ? (source as Record<string, unknown>) : null;
}

function artifactValue(source: Record<string, unknown>, field: string): unknown {
  if (field === "surface_ast") {
    return source.surface_ast ?? source.ast;
  }
  return source[field];
}

export function createUnsupportedWorkspaceAdapter(): WorkspaceAdapter {
  return {
    async listWorkspace() {
      return { ok: false, error: unsupportedPlatformError("workspace.listWorkspace") };
    },
    async readFile(request) {
      return {
        ok: false,
        error: unsupportedPlatformError("workspace.readFile", request.relativePath),
      };
    },
    async saveFile(request) {
      return {
        ok: false,
        error: unsupportedPlatformError("workspace.saveFile", request.relativePath),
      };
    },
  };
}

export function createUnsupportedArtifactAdapter(): ArtifactAdapter {
  return {
    async getArtifactIndex(_request: ArtifactIndexRequest) {
      return { ok: false, error: unsupportedPlatformError("artifacts.getArtifactIndex") };
    },
    async readArtifact(request: ReadArtifactRequest) {
      return {
        ok: false,
        error: unsupportedPlatformError("artifacts.readArtifact", request.relativePath),
      };
    },
  };
}

export function createUnsupportedCommandAdapter(): CommandAdapter {
  return {
    async execute(command: IdeCommand) {
      return { ok: false, error: unsupportedPlatformError(`commands.${command}`) };
    },
  };
}

export function createMemorySettingsAdapter(): SettingsAdapter {
  const settings = new Map<string, unknown>();

  return {
    async get<T>(key: string): Promise<T | null> {
      return settings.has(key) ? (settings.get(key) as T) : null;
    },
    async set<T>(key: string, value: T): Promise<void> {
      settings.set(key, value);
    },
  };
}

export function createConsoleNotificationAdapter(): NotificationAdapter {
  return {
    info(message: string) {
      console.info(message);
    },
    warning(message: string) {
      console.warn(message);
    },
    error(message: string) {
      console.error(message);
    },
  };
}

export function createBrowserWorkspaceAdapter(): WorkspaceAdapter {
  return {
    async listWorkspace(request) {
      const result = await postJson<{
        root: string;
        files: BackendWorkspaceNode[];
        scan_status?: unknown;
      }>("workspace.listWorkspace", "/api/workspace/list", {
        workspace_root: request.workspaceRoot,
      });

      if (!result.ok) {
        return result;
      }

      return {
        ok: true,
        root: result.root,
        files: result.files.map(mapWorkspaceNode),
        scanStatus: mapScanStatus(result.scan_status),
      };
    },

    async readFile(request) {
      const pathResult = validateNormalizedRelativePath(request.relativePath);
      if (!pathResult.ok) {
        return pathResult;
      }

      const result = await postJson<{
        relative_path: string;
        content: string;
        version?: string;
        read_only?: boolean;
      }>("workspace.readFile", "/api/workspace/read", {
        workspace_root: request.workspaceRoot,
        relative_path: pathResult.relativePath,
      });

      if (!result.ok) {
        return result;
      }

      return {
        ok: true,
        relativePath: pathResult.relativePath,
        content: result.content,
        version: result.version,
        readOnly: result.read_only,
      };
    },

    async saveFile(request) {
      const pathResult = validateNormalizedRelativePath(request.relativePath);
      if (!pathResult.ok) {
        return pathResult;
      }

      const result = await postJson<{
        relative_path: string;
        version?: string;
      }>("workspace.saveFile", "/api/workspace/save", {
        workspace_root: request.workspaceRoot,
        relative_path: pathResult.relativePath,
        content: request.content,
        expected_version: request.expectedVersion,
      });

      if (!result.ok) {
        return result;
      }

      return {
        ok: true,
        relativePath: pathResult.relativePath,
        version: result.version,
      };
    },
  };
}

export function createBrowserArtifactAdapter(): ArtifactAdapter {
  return {
    async getArtifactIndex(request: ArtifactIndexRequest) {
      if (request.relativePath) {
        const pathResult = validateNormalizedRelativePath(request.relativePath);
        if (!pathResult.ok) return pathResult;
      }

      const source = analyzeArtifactSource;
      if (!source) {
        return {
          ok: true,
          artifacts: ARTIFACT_FIELDS.map(({ name, fileName }) => ({
            name,
            fileName,
            state: "unavailable",
            relativePath: request.relativePath,
            artifactId: request.artifactId,
          })),
        };
      }

      const artifacts = ARTIFACT_FIELDS.map<ArtifactDescriptor>(({ name, fileName, field }) => {
        const value = artifactValue(source, field);
        return {
          name,
          fileName,
          state: value == null ? "unavailable" : "available",
          relativePath: request.relativePath,
          artifactId: request.artifactId,
        };
      });

      return { ok: true, artifacts };
    },

    async readArtifact(request: ReadArtifactRequest) {
      if (request.relativePath) {
        const pathResult = validateNormalizedRelativePath(request.relativePath);
        if (!pathResult.ok) return pathResult;
      }

      const source = analyzeArtifactSource;
      if (!source) {
        return {
          ok: false,
          error: createPlatformError("missing", "No analyze result is available for artifact reads.", {
            operation: "artifacts.readArtifact",
            relativePath: request.relativePath,
          }),
        };
      }

      const match = ARTIFACT_FIELDS.find((artifact) => artifact.fileName === request.fileName);
      if (!match) {
        return {
          ok: false,
          error: createPlatformError("missing", `Unknown artifact file: ${request.fileName}`, {
            operation: "artifacts.readArtifact",
            relativePath: request.relativePath,
          }),
        };
      }

      const content = artifactValue(source, match.field);
      if (content == null) {
        return {
          ok: false,
          error: createPlatformError("missing", `Artifact is unavailable: ${request.fileName}`, {
            operation: "artifacts.readArtifact",
            relativePath: request.relativePath,
          }),
        };
      }

      return {
        ok: true,
        fileName: request.fileName,
        content,
        rawText: JSON.stringify(content, null, 2),
      };
    },
  };
}

export function createBrowserPlatformAdapter(): PlatformAdapter {
  return {
    environment: {
      kind: "browser",
      os: "unknown",
      supportsLocalFilesystem: false,
      supportsNativeDialogs: false,
      supportsNativeMenu: false,
      supportsProcessExecution: false,
    },
    workspace: createBrowserWorkspaceAdapter(),
    artifacts: createBrowserArtifactAdapter(),
    commands: createUnsupportedCommandAdapter(),
    settings: createMemorySettingsAdapter(),
    notifications: createConsoleNotificationAdapter(),
  };
}
