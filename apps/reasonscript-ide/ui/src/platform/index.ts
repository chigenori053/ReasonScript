export { createBrowserPlatformAdapter } from "./browserAdapter";
export { createDesktopPlatformAdapter } from "./desktopAdapter";
export type {
  ArtifactAdapter,
  ArtifactDescriptor,
  ArtifactIndexRequest,
  ArtifactIndexResult,
  CommandAdapter,
  CommandResult,
  IdeCommand,
  ListWorkspaceRequest,
  ListWorkspaceResult,
  NormalizedRelativePath,
  NotificationAdapter,
  PlatformAdapter,
  PlatformEnvironment,
  PlatformError,
  PlatformErrorKind,
  PlatformKind,
  PlatformOS,
  ReadArtifactRequest,
  ReadArtifactResult,
  ReadWorkspaceFileRequest,
  ReadWorkspaceFileResult,
  SaveWorkspaceFileRequest,
  SaveWorkspaceFileResult,
  SettingsAdapter,
  WorkspaceAdapter,
  WorkspaceFileNode,
} from "./types";
export { isNormalizedRelativePath, validateNormalizedRelativePath } from "./types";

import { createBrowserPlatformAdapter } from "./browserAdapter";
import { setBrowserAnalyzeArtifactSource } from "./browserAdapter";
import type { PlatformAdapter } from "./types";

let activeAdapter: PlatformAdapter | null = null;

export function getPlatformAdapter(): PlatformAdapter {
  if (!activeAdapter) {
    activeAdapter = createBrowserPlatformAdapter();
  }
  return activeAdapter;
}

export function setAnalyzeArtifactSource(source: unknown): void {
  setBrowserAnalyzeArtifactSource(source);
}
