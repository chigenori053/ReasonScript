"""Compiled artifact identity, trusted local build records and validated loading.

The target directory is untrusted cache storage. Source files and .reason/trusted-builds
are the local publisher trust boundary; writers to both are outside this contract.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import tempfile
from pathlib import Path
from typing import Any

IR_SCHEMA = 'reason-computation-ir/0.2'
RUNTIME_ABI = 'reasonscript-runtime/1.0'
BUILD_SCHEMA = 'reasonscript-compiled-build/1.0'
ROOT = Path(__file__).resolve().parents[1]

class ArtifactError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)

def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def read_json(raw: bytes) -> Any:
    def nonfinite(value: str) -> None:
        raise ValueError(f'non-finite JSON value: {value}')
    return json.loads(raw, parse_constant=nonfinite)

def atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.build-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)

def compilation_identity(project_root: Path, dependency_roots: tuple[Path, ...] = (), *, project_sources: tuple[Path, ...] = (), project_contents: dict[Path, bytes] | None = None) -> dict[str, Any]:
    from .manifest import Manifest
    from .source_selection import package_sources
    from frontend.computation_ir.rust_bridge import find_binary
    packages = []
    for root in (project_root, *dependency_roots):
        sources = project_sources if root == project_root and project_sources else tuple(package_sources(root, Manifest.load(root)))
        packages.append({'manifest': (root/'reason.toml').read_text(), 'sources': [
            {'path': p.relative_to(root).as_posix(), 'sha256': sha(project_contents[p] if root == project_root and project_contents is not None else p.read_bytes())} for p in sources
        ]})
    files = [p for folder in ['frontend', 'conformance', 'toolchain'] for p in (ROOT/folder).rglob('*.py') if '__pycache__' not in p.parts]
    compiler = sha(canonical({str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted(files)}))
    binary = find_binary()
    return {'schema': BUILD_SCHEMA, 'version': (ROOT/'VERSION').read_text().strip(),
            'compiler': compiler, 'python': platform.python_version(),
            'runtime_binary': sha(binary.read_bytes()) if binary else None,
            'runtime_abi': RUNTIME_ABI, 'ir_schema': IR_SCHEMA, 'serialization': 'json/1',
            'options': {'optimize': True}, 'packages': packages}

def compilation_key(project_root: Path, dependency_roots: tuple[Path, ...] = (), *, project_sources: tuple[Path, ...] = ()) -> str:
    return sha(canonical(compilation_identity(project_root, dependency_roots, project_sources=project_sources)))

def publish(project: Path, identity: dict[str, Any], raw: bytes) -> None:
    key = sha(canonical(identity))
    record = {'schema': BUILD_SCHEMA, 'identity': identity, 'key': key, 'artifact_sha256': sha(raw)}
    # Commit the trusted record last. Partial publication never becomes executable.
    atomic_write(project/'target/runtime/build_manifest.json', canonical(record))
    atomic_write(project/'.reason/trusted-builds'/f'{key}.json', canonical(record))
    atomic_write(project/'target/.reason_build_cache', key.encode())

def load(project: Path, dependency_roots: tuple[Path, ...] = (), *, frozen: bool = False, identity: dict[str, Any] | None = None) -> dict[str, Any]:
    from frontend.computation_ir import validate_program
    try:
        record = read_json((project/'target/runtime/build_manifest.json').read_bytes())
        key = record['key']
        if not isinstance(key, str) or len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('invalid build identity key')
        trusted = read_json((project/'.reason/trusted-builds'/f'{key}.json').read_bytes())
        if record != trusted or key != sha(canonical(record['identity'])):
            raise ArtifactError('RTH-IR-INTEGRITY', 'build manifest does not match the trusted local build record')
        if record['schema'] != BUILD_SCHEMA or record['identity']['runtime_abi'] != RUNTIME_ABI or record['identity']['ir_schema'] != IR_SCHEMA:
            raise ArtifactError('RTH-IR-ABI', 'compiled artifact format or ABI is incompatible')
        if not frozen and record['identity'] != (identity or compilation_identity(project, dependency_roots)):
            raise ArtifactError('RTH-IR-STALE', 'compiled artifact is stale; run reason build')
        raw = (project/'target/computation_ir/package.json').read_bytes()
        if sha(raw) != record['artifact_sha256']:
            raise ArtifactError('RTH-IR-INTEGRITY', 'compiled artifact content hash mismatch')
        document = read_json(raw)
        errors = validate_program(document)
        if errors:
            raise ValueError('; '.join(errors))
        if document.get('runtime_abi') != RUNTIME_ABI:
            raise ArtifactError('RTH-IR-ABI', 'compiled artifact runtime ABI mismatch')
        return document
    except ArtifactError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise ArtifactError('RTH-IR-INVALID', f'compiled artifact or trusted build record is invalid: {error}') from error
