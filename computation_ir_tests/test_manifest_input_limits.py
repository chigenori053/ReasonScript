"""Project input limits reach the production CLI and retain bounded defaults."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
from toolchain.manifest import Manifest, ManifestError

ROOT = Path(__file__).resolve().parents[1]


def project(root, settings=''):
    (root/'reason.toml').write_text('[package]\nname="inputs"\nversion="0.1.0"\n[runtime]\n'+settings)
    (root/'src').mkdir(exist_ok=True)
    (root/'src/main.rsn').write_text('module M {\n pub fn Length(values: [int]) -> int { return values.length }\n}\n')


@pytest.mark.parametrize('key,ceiling', [('max_input_elements',10_000_000), ('max_input_bytes',1_073_741_824)])
def test_manifest_bounds(tmp_path, key, ceiling):
    for invalid in ('0', '-1', 'true', '1.5', '"100"', str(ceiling+1)):
        project(tmp_path, f'{key}={invalid}\n')
        with pytest.raises(ManifestError):
            Manifest.load(tmp_path)
    project(tmp_path, f'{key}={ceiling}\n')
    assert getattr(Manifest.load(tmp_path), key) == ceiling


def test_cli_admits_large_input_only_when_configured(tmp_path):
    inputs = tmp_path/'inputs.json'; inputs.write_text(json.dumps({'values':[1]*100_000}))
    command = [sys.executable, str(ROOT/'reason'), 'run', 'src/main.rsn',
               '--entry', 'Length', '--inputs', str(inputs), '--json']
    project(tmp_path)
    rejected = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert rejected.returncode != 0 and 'RTH-INPUT-001' in rejected.stdout
    project(tmp_path, 'max_input_elements=100001\nmax_input_bytes=1000000\n')
    admitted = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert admitted.returncode == 0, admitted.stdout + admitted.stderr
    assert json.loads(admitted.stdout)['runtime_result']['result'] == 100_000
