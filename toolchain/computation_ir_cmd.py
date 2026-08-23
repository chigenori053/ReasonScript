"""CLI wrapper for `reason computation-ir` (reason-computation-ir/0.1, Phase 2)."""

from __future__ import annotations

import sys
from pathlib import Path

from frontend.computation_ir import lower_program, validate_program
from frontend.language_surface import parse
from toolchain.diagnostics import stable_json as render_json


def run(command: str, args: list[str], project_root: Path) -> int:
    json_output = "--json" in args
    validate_only = "--validate" in args
    source_path = _path_arg(args)
    if source_path is None:
        print("Usage: reason computation-ir [--json] [--validate] <file.rsn>")
        return 1

    source = Path(source_path).read_text(encoding="utf-8")
    program = parse(source)
    ir = lower_program(program)
    errors = validate_program(ir)

    if validate_only:
        if json_output:
            print(render_json({"ok": not errors, "errors": errors}), end="")
        else:
            if errors:
                print(f"reason-computation-ir/0.1 validation FAILED ({len(errors)} error(s)):")
                for error in errors:
                    print(f"  - {error}")
            else:
                print("reason-computation-ir/0.1 validation OK")
        return 0 if not errors else 1

    if errors:
        print("Warning: lowered IR failed structural validation:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
    if json_output:
        print(render_json(ir), end="")
    else:
        print(f"functions: {len(ir['functions'])}")
        print(f"calculations: {', '.join(ir['calculations'])}")
    return 0


def _path_arg(args: list[str]) -> str | None:
    for arg in args:
        if not arg.startswith("--"):
            return arg
    return None
