import type { PlatformAdapter } from "./types";
import {
  createConsoleNotificationAdapter,
  createMemorySettingsAdapter,
  createUnsupportedArtifactAdapter,
  createUnsupportedCommandAdapter,
  createUnsupportedWorkspaceAdapter,
} from "./browserAdapter";

export function createDesktopPlatformAdapter(): PlatformAdapter {
  return {
    environment: {
      kind: "desktop",
      os: "unknown",
      supportsLocalFilesystem: true,
      supportsNativeDialogs: true,
      supportsNativeMenu: true,
      supportsProcessExecution: false,
    },
    workspace: createUnsupportedWorkspaceAdapter(),
    artifacts: createUnsupportedArtifactAdapter(),
    commands: createUnsupportedCommandAdapter(),
    settings: createMemorySettingsAdapter(),
    notifications: createConsoleNotificationAdapter(),
  };
}
