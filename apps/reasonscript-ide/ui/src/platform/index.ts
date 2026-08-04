export { createBrowserPlatformAdapter } from "./browserAdapter";
export { createDesktopPlatformAdapter } from "./desktopAdapter";
export { createCommandRegistry, createCommandResult } from "./commandRegistry";
export type { CommandHandler, CommandRegistry } from "./commandRegistry";
export { IDE_SHORTCUT_BINDINGS } from "./shortcuts";
export type { IdeShortcutBinding } from "./shortcuts";
export type {
  ArtifactAdapter,
  ArtifactDescriptor,
  ArtifactIndexRequest,
  ArtifactIndexResult,
  CommandAdapter,
  CommandRequest,
  CommandResult,
  IdeCommand,
  IdeSettingKey,
  ListWorkspaceRequest,
  ListWorkspaceResult,
  NormalizedRelativePath,
  NotificationAdapter,
  NotificationOptions,
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
export { notifyPlatformError } from "./browserAdapter";

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
