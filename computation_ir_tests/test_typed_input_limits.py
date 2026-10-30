"""Opt-in input admission, through the production native request API."""
import json
import subprocess

import pytest
from jsonschema import Draft202012Validator
from pathlib import Path
from frontend.computation_ir import lower_program
from frontend.language_surface import parse
from frontend.computation_ir.rust_bridge import find_binary, run_ir

HOST = find_binary()
pytestmark = pytest.mark.skipif(HOST is None, reason="native host not built")


def program():
    return lower_program(parse('''module InputLimits {
 pub fn Length(values: [int]) -> int { return values.length }
 pub fn Echo(value: string) -> string { return value }
}'''))


def test_default_compatibility_and_opt_in_extension():
    ir = program(); inputs = {'values':[1]*100_000}
    assert run_ir(ir, entry='Length', inputs=inputs).error_code == 'RTH-INPUT-001'
    a = run_ir(ir, entry='Length', inputs=inputs, limits={'max_input_elements':100_001,'max_input_bytes':1_000_000})
    assert a.ok and list(a.calculation_results.values()) == [100_000]
    assert run_ir(ir, entry='Length', inputs={'values':[2]}, limits={}).calculation_results == run_ir(ir, entry='Length', inputs={'values':[2]}).calculation_results


@pytest.mark.parametrize('name,value',[(k,v) for k in ('max_input_elements','max_input_bytes') for v in (0,-1,True,1.5,'1000',None,2**64)])
def test_invalid_settings_are_protocol_errors(name,value):
    result=run_ir(program(),entry='Length',inputs={'values':[]},limits={name:value})
    assert not result.ok and result.error_code == 'RTH-PROTO-004'


@pytest.mark.parametrize('limits',[{'max_input_elements':10_000_001},{'max_input_bytes':1_073_741_825}])
def test_settings_cannot_exceed_hard_ceiling(limits):
    assert run_ir(program(),entry='Length',inputs={'values':[]},limits=limits).error_code == 'RTH-PROTO-004'


def test_byte_limit_utf8_boundary_and_strict_type():
    ir=program(); inputs={'value':'界\n"'}
    n=len(json.dumps(inputs,ensure_ascii=False,separators=(',',':')).encode())
    assert run_ir(ir,entry='Echo',inputs=inputs,limits={'max_input_bytes':n}).ok
    assert run_ir(ir,entry='Echo',inputs=inputs,limits={'max_input_bytes':n-1}).error_code == 'RTH-INPUT-001'
    assert run_ir(ir,entry='Length',inputs={'values':[True]},limits={'max_input_elements':5_000_000}).error_code == 'RTH-INPUT-001'


def test_new_optional_schema_fields_preserve_other_limits():
    schema=json.loads((Path(__file__).resolve().parents[1]/'schemas/runtime_request.schema.json').read_text())
    limits=schema['properties']['context']['properties']['limits']
    Draft202012Validator(limits).validate({'max_input_elements':5_000_000,'max_input_bytes':536_870_912,'max_loop_iterations':12})
    assert list(Draft202012Validator(limits).iter_errors({'max_input_elements':0}))
    assert not list(Draft202012Validator(limits).iter_errors({}))
