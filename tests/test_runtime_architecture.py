"""IR trust boundaries and typed dynamic input behavior, through the native VM."""
import contextlib
import io
import json
from pathlib import Path

import pytest
from frontend.language_surface import parse
from frontend.computation_ir import lower_program
from frontend.computation_ir.rust_bridge import run_ir
from toolchain import build_cmd, run_cmd
from toolchain.compiled_ir import ArtifactError, load, read_json

SOURCE = '''module Test {
 struct Evidence { valid: bool }
 struct Unknown { owner: string }
 struct Knowledge { weight: float }
 struct World { knowledge: Knowledge evidence: Evidence unknowns: [Unknown] }
 pub fn Evaluate(state: World, offset: int, label: string) -> float {
  if state.evidence.valid {
   return state.knowledge.weight + float(offset)
  }
  return 0.0
 }
 pub fn Mutate(xs: [int]) -> int {
  let local = xs
  local[0] = local[0] + 1
  return local[0]
 }
 calculation Main {
  result = 42
 }
}
'''.replace('struct World { knowledge: Knowledge evidence: Evidence unknowns: [Unknown] }', 'struct World {\n knowledge: Knowledge\n evidence: Evidence\n unknowns: [Unknown]\n }')

def test_dynamic_structures_isolated_and_strict():
    ir = lower_program(parse(SOURCE))
    value = dict(state=dict(knowledge={'weight':2.5},evidence={'valid':True},unknowns=[{'owner':'URU:1'}]),offset=3,label='one')
    a = run_ir(ir, entry='Evaluate', inputs=value)
    assert a.ok and list(a.calculation_results.values()) == [5.5]
    value['state']['evidence']['valid'] = False
    b = run_ir(ir, entry='Test::Evaluate', inputs=value)
    assert b.ok and list(b.calculation_results.values()) == [0.0]
    for _ in range(2):
        r = run_ir(ir, entry='Mutate', inputs={'xs':[4]})
        assert r.ok and list(r.calculation_results.values()) == [5]
    value['offset'] = True
    assert run_ir(ir, entry='Evaluate', inputs=value).error_code == 'RTH-INPUT-001'
    value['offset'] = 3
    value['state']['unknowns'][0]['extra'] = 'rejected'
    assert not run_ir(ir, entry='Evaluate', inputs=value).ok

@pytest.mark.parametrize('field,value', [('schema','reason-computation-ir/999'),('runtime_abi','reasonscript-runtime/999')])
def test_native_rejects_incompatible_ir(field, value):
    ir = lower_program(parse(SOURCE));ir[field]=value
    assert run_ir(ir).error_code == 'IR-DECODE-001'

def project(tmp_path):
    (tmp_path/'src').mkdir()
    (tmp_path/'reason.toml').write_text('[package]\nname="test"\nversion="0.1.0"\n')
    (tmp_path/'src/main.rsn').write_text(SOURCE)
    with contextlib.redirect_stdout(io.StringIO()):assert build_cmd.run(tmp_path) == 0
    return tmp_path

def test_stale_frozen_and_tamper(tmp_path):
    p=project(tmp_path);before=load(p)
    src=p/'src/main.rsn';src.write_text(src.read_text().replace('42','43'))
    with pytest.raises(ArtifactError,match='stale'):load(p)
    assert load(p,frozen=True) == before
    with contextlib.redirect_stdout(io.StringIO()):assert run_cmd.run(p,auto_build=True) == 0
    assert load(p) != before
    artifact=p/'target/computation_ir/package.json';artifact.write_bytes(artifact.read_bytes()+b' ')
    with pytest.raises(ArtifactError,match='hash mismatch'):load(p)
    # Rehashing an attacker-controlled cache manifest cannot authenticate changed IR.
    manifest=p/'target/runtime/build_manifest.json';record=json.loads(manifest.read_text())
    from toolchain.compiled_ir import sha
    record['artifact_sha256']=sha(artifact.read_bytes());manifest.write_text(json.dumps(record))
    with pytest.raises(ArtifactError,match='trusted'):load(p)

def test_dependency_and_option_identity(tmp_path):
    p=project(tmp_path)
    src=p/'src/main.rsn';src.write_text(src.read_text()+'\n// dependency/source change\n')
    with pytest.raises(ArtifactError):load(p)
    assert load(p,frozen=True)
    with pytest.raises(ValueError):read_json(b'{"bad":NaN}')

def test_dependency_closure_and_source_snapshot(tmp_path, monkeypatch):
    p=project(tmp_path)
    dep=tmp_path/'dependency';(dep/'src').mkdir(parents=True)
    (dep/'reason.toml').write_text('[package]\nname="dependency"\nversion="0.1.0"\n')
    (dep/'src/module.rsn').write_text('module Dependency {\n fn Value() -> int { return 1 }\n}\n')
    with contextlib.redirect_stdout(io.StringIO()):assert build_cmd._run_package(p,(dep,)) == 0
    assert load(p,(dep,))
    (dep/'src/module.rsn').write_text('// changed dependency\n'+(dep/'src/module.rsn').read_text())
    with pytest.raises(ArtifactError,match='stale'):load(p,(dep,))
    original=build_cmd.compile_package_sources
    def changing(sources):
        result=original(sources)
        path=p/'src/main.rsn';path.write_text(path.read_text().replace('42','43'))
        return result
    monkeypatch.setattr(build_cmd,'compile_package_sources',changing)
    with contextlib.redirect_stdout(io.StringIO()) as buf:assert build_cmd._run_package(p,(dep,)) == 1
    assert 'changed during build' in buf.getvalue()

def test_dynamic_project_cli(tmp_path, monkeypatch):
    p=project(tmp_path);monkeypatch.chdir(p)
    inputs=p/'input.json';inputs.write_text('{"xs":[10]}')
    from toolchain.__main__ import main
    import sys
    monkeypatch.setattr(sys,'argv',['reason','run','--entry','Mutate','--inputs',str(inputs),'--trace=off'])
    with contextlib.redirect_stdout(io.StringIO()) as buf:assert main() == 0
    assert json.loads(buf.getvalue())['runtime_result']['result'] == 11
