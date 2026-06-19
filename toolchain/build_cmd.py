"""reason build — compile source files to AST, IR, and metadata."""

from __future__ import annotations

import json
from pathlib import Path

from .manifest import Manifest, ManifestError
from .pipeline import PipelineError, compile_source

_CACHE_KEY_FILE = ".reason_build_cache"


def _cache_key(project_root: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    manifest_path = project_root / "reason.toml"
    if manifest_path.exists():
        h.update(manifest_path.read_bytes())
    for src in sorted((project_root / "src").rglob("*.rsn")):
        h.update(src.read_bytes())
    return h.hexdigest()


def _load_cache(target: Path) -> str:
    p = target / _CACHE_KEY_FILE
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def _save_cache(target: Path, key: str) -> None:
    (target / _CACHE_KEY_FILE).write_text(key, encoding="utf-8")


def run(project_root: Path) -> int:
    try:
        manifest = Manifest.load(project_root)
    except ManifestError as e:
        print(f"Error:\n\n{e}")
        return 1

    src_dir = project_root / "src"
    if not src_dir.exists():
        print("Error:\n\nSourceDirectoryMissing\n\nsrc/ not found.")
        return 1

    sources = sorted(src_dir.rglob("*.rsn"))
    if not sources:
        print("Error:\n\nNoSourceFiles\n\nNo .rsn files found in src/.")
        return 1

    target = project_root / "target"
    current_key = _cache_key(project_root)
    if _load_cache(target) == current_key:
        print("Nothing to build (up to date).")
        return 0

    ast_dir = target / "ast"
    ir_dir = target / "ir"
    meta_dir = target / "metadata"
    for d in (ast_dir, ir_dir, meta_dir, target / "runtime"):
        d.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    for src_path in sources:
        source = src_path.read_text(encoding="utf-8")
        try:
            result = compile_source(source, src_path)
        except PipelineError as e:
            errors.append(f"{src_path}: {e.code}: {e.message}")
            continue

        stem = src_path.stem
        for ir in result.reason_irs:
            module_name = ir.get("module") or stem
            (ir_dir / f"{module_name}.json").write_text(
                json.dumps(ir, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            meta = result.metadata_for(ir)
            (meta_dir / f"{module_name}.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
            )

        ast_payload = {
            "package": manifest.name,
            "sources": [str(src_path.relative_to(project_root))],
        }
        (ast_dir / f"{stem}.json").write_text(
            json.dumps(ast_payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    if errors:
        for e in errors:
            print(f"Error:\n\n{e}")
        return 1

    _save_cache(target, current_key)
    print(f"Build succeeded. {len(sources)} file(s) compiled.")
    return 0
