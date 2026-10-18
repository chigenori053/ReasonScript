import cmath
import math
import random

import pytest
from frontend.language_surface import parse
from frontend.computation_ir import lower_program
from frontend.computation_ir.optimizer import optimize_program
from frontend.computation_ir.rust_bridge import run_ir

SOURCE='''module ComplexTests {
 pub fn Scalar(op: string, a: Complex, b: Complex) -> Complex {
  if op == "add" {
   return complex.add(a,b)
  }
  if op == "sub" {
   return complex.sub(a,b)
  }
  if op == "mul" {
   return complex.mul(a,b)
  }
  if op == "conjugate" {
   return complex.conjugate(a)
  }
  return complex.div(a,b)
 }
 pub fn Polar(a: Complex) -> [float] {
  return [complex.abs(a),complex.phase(a)]
 }
 pub fn Vector(op: string, a: [Complex], b: [Complex], factor: Complex) -> [Complex] {
  if op == "add" {
   return complex.vector_add(a,b)
  }
  if op == "sub" {
   return complex.vector_sub(a,b)
  }
  return complex.scale(a,factor)
 }
 pub fn Inner(a: [Complex], b: [Complex]) -> Complex { return complex.inner(a,b) }
 pub fn Matrix(a: [[Complex]], b: [[Complex]]) -> [[Complex]] { return complex.matmul(a,b) }
 pub fn Transition(s: ComplexState, m: [[Complex]]) -> ComplexState { return complex.transition(s,m) }
 pub fn Create() -> ComplexState { return complex.state([complex.scalar(1.0,0.0),complex.scalar(0.0,1.0)]) }
}
'''

@pytest.fixture(scope='module')
def ir():return optimize_program(lower_program(parse(SOURCE)))
def z(v):return {'re':v.real,'im':v.imag}
def unwrap(v):
    if isinstance(v,dict):return unwrap(v['fields']) if 'fields' in v and 'type_name' in v else {k:unwrap(x) for k,x in v.items()}
    if isinstance(v,list):return [unwrap(x) for x in v]
    return v
def execute(ir,entry,inputs,**kw):
    r=run_ir(ir,entry=entry,inputs=inputs,**kw)
    assert r.ok,(r.error_code,r.error_message)
    return unwrap(next(iter(r.calculation_results.values())))
def check(actual, expected):
    assert actual['re']==pytest.approx(expected.real,rel=1e-12,abs=1e-12)
    assert actual['im']==pytest.approx(expected.imag,rel=1e-12,abs=1e-12)

def test_scalar_reference_and_polar(ir):
    rng=random.Random(20261019)
    for _ in range(4):
        a=complex(rng.uniform(-5,5),rng.uniform(-5,5));b=complex(rng.uniform(-5,5),rng.uniform(-5,5))
        for op,expected in [('add',a+b),('sub',a-b),('mul',a*b),('div',a/b),('conjugate',a.conjugate())]:
            check(execute(ir,'Scalar',dict(op=op,a=z(a),b=z(b))),expected)
        assert execute(ir,'Polar',dict(a=z(a)))==pytest.approx([abs(a),cmath.phase(a)],rel=1e-12)
    assert execute(ir,'Polar',dict(a=z(0j))) == [0.0,0.0]
    check(execute(ir,'Scalar',dict(op='div',a=z(complex(1e308,1e308)),b=z(complex(1e308,1e308)))),1+0j)

def test_vectors_matrices_and_hermitian(ir):
    a=[1+2j,3-1j];b=[-2+1j,4+3j]
    for op,expected in [('add',[x+y for x,y in zip(a,b)]),('sub',[x-y for x,y in zip(a,b)]),('scale',[x*(2+3j) for x in a])]:
        for actual,want in zip(execute(ir,'Vector',dict(op=op,a=list(map(z,a)),b=list(map(z,b)),factor=z(2+3j))),expected):check(actual,want)
    check(execute(ir,'Inner',dict(a=list(map(z,a)),b=list(map(z,b)))),sum(x.conjugate()*y for x,y in zip(a,b)))
    x=[a,b];y=[b,a]
    actual=execute(ir,'Matrix',dict(a=[[z(v) for v in r] for r in x],b=[[z(v) for v in r] for r in y]))
    for i in range(2):
        for j in range(2):check(actual[i][j],sum(x[i][k]*y[k][j] for k in range(2)))

def test_state_transition_determinism_and_trace_budget(ir):
    state=execute(ir,'Create',{})
    matrix=[[z(0j),z(1+0j)],[z(1+0j),z(0j)]]
    inputs=dict(s=state,m=matrix)
    a=run_ir(ir,entry='Transition',inputs=inputs,trace_enabled=True)
    b=run_ir(ir,entry='Transition',inputs=inputs,trace_enabled=True)
    assert a.ok and a.calculation_results==b.calculation_results
    assert a.metadata['complex_trace']==b.metadata['complex_trace']
    assert a.metadata['complex_trace'][0] in a.metadata['trace']
    out=unwrap(next(iter(a.calculation_results.values())))
    assert out['revision']==1 and out['amplitudes']==list(reversed(state['amplitudes']))
    c=run_ir(ir,entry='Transition',inputs=inputs,trace_enabled=True,trace_config={'max_bytes':1})
    assert c.ok and c.calculation_results==a.calculation_results
    assert not c.metadata['complex_trace'] and c.metadata['trace_diagnostics']

@pytest.mark.parametrize('entry,inputs,code',[
 ('Scalar',dict(op='div',a=z(1j),b=z(0j)),'CXR-DIVZERO'),
 ('Scalar',dict(op='add',a=z(complex(1e308,0)),b=z(complex(1e308,0))),'CXR-OVERFLOW'),
 ('Inner',dict(a=[z(1j)],b=[]),'CXR-SHAPE'),
 ('Matrix',dict(a=[[]],b=[]),'CXR-SHAPE'),
 ('Matrix',dict(a=[[z(1j)],[z(1j),z(2j)]],b=[[z(1j)]]),'CXR-SHAPE'),
 ('Polar',dict(a={'re':'bad','im':0.0}),'RTH-INPUT-001'),
 ('Polar',dict(a={'re':float('inf'),'im':0.0}),'IR-DECODE-001'),
 ('Matrix',dict(a=[[z(1j)]]*65,b=[[z(1j)]]),'CXR-LIMIT'),
 ('Transition',dict(s={'amplitudes':[z(1j)],'revision':2**63-1},m=[[z(1+0j)]]),'CXR-OVERFLOW'),
])
def test_numeric_and_shape_safety(ir,entry,inputs,code):
    assert run_ir(ir,entry=entry,inputs=inputs).error_code==code
