import type { IdeCommand } from "./types";

export interface IdeShortcutBinding {
  command: IdeCommand;
  mac?: string;
  windows?: string;
  linux?: string;
}

export const IDE_SHORTCUT_BINDINGS: IdeShortcutBinding[] = [
  {
    command: "saveFile",
    mac: "Cmd+S",
    windows: "Ctrl+S",
    linux: "Ctrl+S",
  },
  {
    command: "analyzeFile",
    mac: "Cmd+Enter",
    windows: "Ctrl+Enter",
    linux: "Ctrl+Enter",
  },
  {
    command: "showProblems",
    mac: "Cmd+Shift+M",
    windows: "Ctrl+Shift+M",
    linux: "Ctrl+Shift+M",
  },
];
