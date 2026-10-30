"""Shared argument reading for the existing lightweight CLI wrappers."""
from pathlib import Path


def option_value(args: list[str], option: str) -> str | None:
    if option not in args:
        return None
    index = args.index(option)
    return args[index + 1] if index + 1 < len(args) else None


def path_arg(args: list[str], default: Path, *, value_options=("--out",)) -> Path:
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in value_options:
            skip_next = True
            continue
        if arg.startswith("--"):
            continue
        return Path(arg)
    return default
