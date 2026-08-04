from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = (
    REPO_ROOT
    / "apps"
    / "reasonscript-ide"
    / "ui"
    / "src"
    / "platform"
    / "commandRegistry.ts"
)


def test_command_registry_contract_exists():
    source = REGISTRY.read_text(encoding="utf-8")

    assert "export type CommandHandler" in source
    assert "export interface CommandRegistry extends CommandAdapter" in source
    assert "register(command: IdeCommand, handler: CommandHandler): void" in source
    assert "has(command: IdeCommand): boolean" in source


def test_command_registry_executes_registered_handler():
    source = REGISTRY.read_text(encoding="utf-8")

    assert "const handlers = new Map<IdeCommand, CommandHandler>()" in source
    assert "handlers.set(command, handler)" in source
    assert "const handler = handlers.get(request.command)" in source
    assert "return await handler(request)" in source


def test_command_registry_unknown_command_returns_unsupported():
    source = REGISTRY.read_text(encoding="utf-8")

    assert "unsupportedPlatformError(`commands.${request.command}`)" in source
    assert "ok: false" in source
    assert "command: request.command" in source
