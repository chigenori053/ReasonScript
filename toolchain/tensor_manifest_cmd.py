"""CLI wrapper for `reason tensor-manifest`."""

from __future__ import annotations

from pathlib import Path

from toolchain.tensor_manifest import (
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
    baseline_path = _option_value(args, "--baseline")
    baseline = Path(baseline_path) if baseline_path else project_root / DEFAULT_BASELINE_PATH

    if check:
        diffs = diff_manifest(baseline)
        if json_output:
            print(stable_json({"ok": not diffs, "baseline": str(baseline), "diffs": diffs}), end="")
        else:
            if diffs:
                print(f"Tensor contract manifest drift detected against {baseline}:")
                for item in diffs:
                    print(f"  - {item}")
            else:
                print(f"Tensor contract manifest matches baseline: {baseline}")
        return 0 if not diffs else 1

    manifest = build_manifest()
    if out_dir is not None:
        write_manifest(Path(out_dir) / "tensor_function_manifest.json")
    if json_output:
        print(stable_json(manifest), end="")
    else:
        print("ReasonScript Tensor function manifest")
        print(f"functions: {manifest['function_count']}")
    return 0


def _option_value(args: list[str], option: str) -> str | None:
    if option not in args:
        return None
    index = args.index(option)
    if index + 1 >= len(args):
        return None
    return args[index + 1]
