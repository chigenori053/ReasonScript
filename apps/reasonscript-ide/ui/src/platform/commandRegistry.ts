import type {
  CommandAdapter,
  CommandRequest,
  CommandResult,
  IdeCommand,
} from "./types";
import { unsupportedPlatformError } from "./types";

export type CommandHandler = (request: CommandRequest) => Promise<CommandResult>;

export interface CommandRegistry extends CommandAdapter {
  register(command: IdeCommand, handler: CommandHandler): void;
  has(command: IdeCommand): boolean;
}

export function createCommandResult(
  request: CommandRequest,
  message?: string
): CommandResult {
  return {
    ok: true,
    command: request.command,
    message,
  };
}

export function createCommandRegistry(): CommandRegistry {
  const handlers = new Map<IdeCommand, CommandHandler>();

  return {
    register(command, handler) {
      handlers.set(command, handler);
    },

    has(command) {
      return handlers.has(command);
    },

    async execute(request) {
      const handler = handlers.get(request.command);
      if (!handler) {
        return {
          ok: false,
          command: request.command,
          error: unsupportedPlatformError(`commands.${request.command}`),
        };
      }

      try {
        return await handler(request);
      } catch (cause) {
        return {
          ok: false,
          command: request.command,
          error: {
            kind: "unknown",
            message: cause instanceof Error ? cause.message : String(cause),
            operation: `commands.${request.command}`,
            cause,
          },
        };
      }
    },
  };
}
