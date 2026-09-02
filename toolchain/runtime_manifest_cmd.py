"""CLI wrapper for ``reason runtime-manifest``."""

from __future__ import annotations

from pathlib import Path

from toolchain.runtime_manifest import (
    DEFAULT_BASELINE_PATH,
    build_manifest,
    diff_manifest,
    stable_json,
    write_manifest,
)


def run(command: str, args: list[str], project_root: Path) -> int:
    json_output = "--json" in args
    check = "--check" in args
    out_dir = _option_value(args, "--out")
    baseline_arg = _option_value(args, "--baseline")
    baseline = Path(baseline_arg) if baseline_arg else project_root / DEFAULT_BASELINE_PATH

    if check:
        diffs = diff_manifest(baseline)
        if json_output:
            print(stable_json({"ok": not diffs, "baseline": str(baseline), "diffs": diffs}), end="")
        elif diffs:
            print(f"Runtime consolidation manifest drift detected against {baseline}:")
            for item in diffs:
                print(f"  - {item}")
        else:
            print(f"Runtime consolidation manifest matches baseline: {baseline}")
        return 0 if not diffs else 1

    manifest = build_manifest()
    if out_dir is not None:
        write_manifest(Path(out_dir) / "runtime_consolidation_manifest.json")
    if json_output:
        print(stable_json(manifest), end="")
    else:
        operations = sum(len(items) for items in manifest["namespaces"].values())
        print("ReasonScript Runtime consolidation manifest")
        print(f"operations: {operations}")
    return 0


def _option_value(args: list[str], option: str) -> str | None:
    if option not in args:
        return None
    index = args.index(option)
    return args[index + 1] if index + 1 < len(args) else None
