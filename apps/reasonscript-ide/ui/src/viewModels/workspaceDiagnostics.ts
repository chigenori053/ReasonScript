import type { PlatformDiagnostic, WorkspaceScanStatus, WorkspaceState } from "../types";

export interface WorkspaceDiagnosticsViewModel {
  available: boolean;
  scanStatus: WorkspaceScanStatus | "unavailable";
  rootPath?: string;
  validFileCount: number;
  invalidFileCount: number;
  unsupportedFileCount: number;
  ignoredPaths: string[];
  scanTruncated: boolean;
  diagnostics: PlatformDiagnostic[];
}

const UNAVAILABLE: WorkspaceDiagnosticsViewModel = {
  available: false,
  scanStatus: "unavailable",
  validFileCount: 0,
  invalidFileCount: 0,
  unsupportedFileCount: 0,
  ignoredPaths: [],
  scanTruncated: false,
  diagnostics: [],
};

const KNOWN_EXTENSIONS = new Set(["rsn", "rs", "py", "ts", "tsx", "json", "toml", "md"]);

interface FileWalkResult {
  valid: number;
  invalid: number;
  unsupported: number;
  ignoredPaths: string[];
}

function walkFiles(node: WorkspaceState["files"][number], into: FileWalkResult): void {
  if (node.is_ignored) {
    into.ignoredPaths.push(node.relative_path);
    return;
  }
  if (node.kind === "directory") {
    node.children.forEach((child) => walkFiles(child, into));
    return;
  }
  if (node.kind !== "file") {
    into.unsupported += 1;
    return;
  }
  const supportedMetadata = node.metadata?.supported;
  if (supportedMetadata === false) {
    into.invalid += 1;
    return;
  }
  if (node.extension && KNOWN_EXTENSIONS.has(node.extension)) {
    into.valid += 1;
  } else {
    into.unsupported += 1;
  }
}

export function buildWorkspaceDiagnosticsViewModel(
  workspace: WorkspaceState | null
): WorkspaceDiagnosticsViewModel {
  if (!workspace) return UNAVAILABLE;

  const walk: FileWalkResult = { valid: 0, invalid: 0, unsupported: 0, ignoredPaths: [] };
  workspace.files.forEach((node) => walkFiles(node, walk));

  const scanTruncated = workspace.scan_status === "partial";
  const diagnostics: PlatformDiagnostic[] = [];

  if (workspace.scan_status === "failed") {
    diagnostics.push({
      severity: "error",
      message: `Workspace scan failed for ${workspace.root_path}.`,
      stage: "workspace_scan",
      phase: "analyzer",
      source: "workspace",
      related_information: [],
      metadata: { relativePath: undefined },
    });
  } else if (scanTruncated) {
    diagnostics.push({
      severity: "warning",
      message: "Workspace scan truncated: scan limit reached before all files were indexed.",
      stage: "workspace_scan",
      phase: "analyzer",
      source: "workspace",
      related_information: [],
      metadata: { relativePath: undefined },
    });
  }

  if (walk.invalid > 0) {
    diagnostics.push({
      severity: "warning",
      message: `${walk.invalid} invalid file(s) found in workspace.`,
      stage: "workspace_scan",
      phase: "analyzer",
      source: "workspace",
      related_information: [],
      metadata: { relativePath: undefined },
    });
  }

  return {
    available: true,
    scanStatus: workspace.scan_status,
    rootPath: workspace.root_path,
    validFileCount: walk.valid,
    invalidFileCount: walk.invalid,
    unsupportedFileCount: walk.unsupported,
    ignoredPaths: walk.ignoredPaths,
    scanTruncated,
    diagnostics,
  };
}

export function workspaceDiagnosticsAsPlatformDiagnostics(
  vm: WorkspaceDiagnosticsViewModel
): PlatformDiagnostic[] {
  return vm.diagnostics;
}
