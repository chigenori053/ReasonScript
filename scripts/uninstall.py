#!/usr/bin/env python3
"""Manifest-scoped ReasonScript uninstaller."""
import argparse
import json
import os
import shutil
from pathlib import Path

def main() -> int:
    parser = argparse.ArgumentParser()
    default = Path(os.environ.get("REASONSCRIPT_HOME", Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ReasonScript" if os.name == "nt" else Path.home() / ".reasonscript"))
    parser.add_argument("--prefix", type=Path, default=default)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--purge", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = args.prefix.expanduser().resolve()
    manifest_path = root / "install_manifest.json"
    if not manifest_path.is_file():
        print(json.dumps({"status": "failure", "diagnostics": [{"code": "IF-017", "message": "Install manifest not found."}]}))
        return 3
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if Path(manifest.get("install_root", "")).resolve() != root:
        print("IF-017: Install manifest root mismatch.")
        return 3
    targets = [root / "versions", root / "current", root / "bin", manifest_path]
    if args.purge:
        targets.extend([root / "cache", root / "config", root / "artifacts"])
    result = {"status": "success", "dry_run": args.dry_run, "paths": [str(p) for p in targets]}
    if not args.dry_run:
        for path in targets:
            if path.is_symlink() or path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                shutil.rmtree(path)
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else "\n".join(result["paths"]))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
