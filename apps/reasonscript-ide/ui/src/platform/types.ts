export type PlatformKind = "browser" | "desktop";

export type PlatformOS = "macos" | "windows" | "linux" | "unknown";

export interface PlatformEnvironment {
  kind: PlatformKind;
  os: PlatformOS;
  supportsLocalFilesystem: boolean;
  supportsNativeDialogs: boolean;
  supportsNativeMenu: boolean;
  supportsProcessExecution: boolean;
}

export type NormalizedRelativePath = string;

export type PlatformErrorKind =
  | "missing"
  | "read_only"
  | "permission_denied"
  | "invalid_encoding"
  | "path_traversal"
  | "conflict"
  | "unsupported"
  | "network_error"
  | "unknown";

export interface PlatformError {
  kind: PlatformErrorKind;
  message: string;
  operation?: string;
  relativePath?: NormalizedRelativePath;
  cause?: unknown;
}

export interface PlatformFailure {
  ok: false;
  error: PlatformError;
}

export type PlatformResult<T> = ({ ok: true } & T) | PlatformFailure;

export interface WorkspaceFileNode {
  name: string;
  relativePath: NormalizedRelativePath;
  kind: "file" | "directory";
  children?: WorkspaceFileNode[];
  supported?: boolean;
  dirty?: boolean;
  missing?: boolean;
  readOnly?: boolean;
  isSource?: boolean;
  isIgnored?: boolean;
  extension?: string | null;
  isDirectory?: boolean;
  path?: NormalizedRelativePath;
  relative_path?: NormalizedRelativePath;
  is_ignored?: boolean;
}

export interface ListWorkspaceRequest {
  workspaceRoot: string;
}

export type ListWorkspaceResult = PlatformResult<{
  root: string;
  files: WorkspaceFileNode[];
  scanStatus: WorkspaceScanStatus;
}>;

export interface WorkspaceScanStatus {
  status: "success" | "warning" | "error";
  truncated: boolean;
  maxDepth: number;
  maxFiles: number;
  message?: string;
}

export interface ReadWorkspaceFileRequest {
  workspaceRoot: string;
  relativePath: NormalizedRelativePath;
}

export type ReadWorkspaceFileResult = PlatformResult<{
  relativePath: NormalizedRelativePath;
  content?: string;
  version?: string;
  readOnly?: boolean;
  missing?: boolean;
}>;

export interface SaveWorkspaceFileRequest {
  workspaceRoot: string;
  relativePath: NormalizedRelativePath;
  content: string;
  expectedVersion?: string;
}

export type SaveWorkspaceFileResult = PlatformResult<{
  relativePath: NormalizedRelativePath;
  version?: string;
}>;

export interface ArtifactIndexRequest {
  workspaceRoot?: string;
  relativePath?: NormalizedRelativePath;
  artifactId?: string;
}

export type ArtifactIndexResult = PlatformResult<{
  artifacts: ArtifactDescriptor[];
}>;

export interface ArtifactDescriptor {
  name: string;
  fileName: string;
  state: "available" | "missing" | "invalid_json" | "skipped" | "unavailable";
  relativePath?: NormalizedRelativePath;
  artifactId?: string;
}

export interface ReadArtifactRequest {
  workspaceRoot?: string;
  relativePath?: NormalizedRelativePath;
  artifactId?: string;
  fileName: string;
}

export type ReadArtifactResult = PlatformResult<{
  fileName: string;
  content?: unknown;
  rawText?: string;
}>;

export type IdeCommand =
  | "openWorkspace"
  | "refreshWorkspace"
  | "saveFile"
  | "analyzeFile"
  | "runCurrentFile"
  | "validateWorkspace"
  | "auditProject"
  | "showOverview"
  | "showPlan"
  | "showSimulation"
  | "showKnowledge"
  | "showArtifacts"
  | "showProblems"
  | "showOutput"
  | "showLogs"
  | "showTests"
  | "clearOutput"
  | "clearNotifications";

export interface CommandRequest {
  command: IdeCommand;
  payload?: unknown;
  source?: "top_bar" | "shortcut" | "menu" | "panel" | "system";
}

export interface CommandResult {
  ok: boolean;
  command: IdeCommand;
  message?: string;
  error?: PlatformError;
}

export type IdeSettingKey =
  | "compilerMode"
  | "rightInspector.activeTab"
  | "bottomToolWindow.activeTab"
  | "bottomToolWindow.visible"
  | "layout.leftPaneWidth"
  | "layout.rightPaneWidth"
  | "layout.bottomPaneHeight"
  | "workspace.lastRoot";

export interface NotificationOptions {
  title?: string;
  operation?: string;
  details?: string;
  durationMs?: number;
}

export interface WorkspaceAdapter {
  listWorkspace(request: ListWorkspaceRequest): Promise<ListWorkspaceResult>;
  readFile(request: ReadWorkspaceFileRequest): Promise<ReadWorkspaceFileResult>;
  saveFile(request: SaveWorkspaceFileRequest): Promise<SaveWorkspaceFileResult>;
}

export interface ArtifactAdapter {
  getArtifactIndex(request: ArtifactIndexRequest): Promise<ArtifactIndexResult>;
  readArtifact(request: ReadArtifactRequest): Promise<ReadArtifactResult>;
}

export interface CommandAdapter {
  execute(request: CommandRequest): Promise<CommandResult>;
}

export interface SettingsAdapter {
  get<T>(key: string): Promise<T | null>;
  set<T>(key: string, value: T): Promise<void>;
  remove?(key: string): Promise<void>;
}

export interface NotificationAdapter {
  info(message: string, options?: NotificationOptions): void;
  warning(message: string, options?: NotificationOptions): void;
  error(message: string, options?: NotificationOptions): void;
}

export interface PlatformAdapter {
  environment: PlatformEnvironment;
  workspace: WorkspaceAdapter;
  artifacts: ArtifactAdapter;
  commands: CommandAdapter;
  settings: SettingsAdapter;
  notifications: NotificationAdapter;
}

export function createPlatformError(
  kind: PlatformErrorKind,
  message: string,
  options: Pick<PlatformError, "operation" | "relativePath" | "cause"> = {}
): PlatformError {
  return {
    kind,
    message,
    ...options,
  };
}

export function unsupportedPlatformError(
  operation: string,
  relativePath?: NormalizedRelativePath
): PlatformError {
  return createPlatformError("unsupported", `Unsupported platform operation: ${operation}`, {
    operation,
    relativePath,
  });
}

export function isNormalizedRelativePath(path: string): path is NormalizedRelativePath {
  if (!path || path.includes("\\")) {
    return false;
  }
  if (path.startsWith("/") || path.startsWith("../") || path === "..") {
    return false;
  }
  if (/^[A-Za-z]:/.test(path)) {
    return false;
  }
  return !path.split("/").some((part) => part === ".." || part === "");
}

export function validateNormalizedRelativePath(path: string): PlatformResult<{
  relativePath: NormalizedRelativePath;
}> {
  if (isNormalizedRelativePath(path)) {
    return { ok: true, relativePath: path };
  }

  return {
    ok: false,
    error: createPlatformError("path_traversal", "Path must be a slash-normalized relative path.", {
      operation: "validateNormalizedRelativePath",
    }),
  };
}
