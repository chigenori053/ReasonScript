"""Native exhaustive and summary inference: shared setup and safety regressions."""
import random
from pathlib import Path
import pytest
from frontend.computation_ir import lower_program
from frontend.computation_ir.optimizer import optimize_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.language_surface import parse, validate

SOURCE = Path(__file__).resolve().parents[1]/'examples/inference_scale/main.rsn'
pytestmark = pytest.mark.skipif(find_binary() is None, reason='native host not built')


def unit(uid, subject, target, status="VERIFIED"):
    return dict(unit_id=uid, unit_kind="RU", semantic_status=status,
                state_representation="discrete", evidence=[uid], dependencies=[],
                proof_path=[], revision=1, provenance=["test"], validation_status="VALID",
                subject=subject, object=target, predicate=1, polarity=1,
                current_revision=1, negative_evidence=[], revoked=False)


def binding(u):
    return dict(evidence_id=u["evidence"][0], **{k: u[k] for k in
                ("unit_id", "subject", "predicate", "object", "polarity", "revision")})


@pytest.fixture(scope='module')
def ir():
    ast = parse(SOURCE.read_text()); validate(ast)
    return optimize_program(lower_program(ast))


def execute(ir, inputs, entry='Summarize'):
    r = run_ir(ir, entry='UnifiedB::'+entry, inputs=inputs,
               limits=dict(max_input_elements=5_000_000, max_input_bytes=536_870_912,
                           max_loop_iterations=10_000_000))
    assert r.ok, (r.error_code, r.error_message)
    value = next(iter(r.calculation_results.values()))
    return value.get('fields',value) if isinstance(value,dict) else value


def request(units, **overrides):
    r = dict(units=units, trusted=[binding(u) for u in units if u['evidence']], entities=[0,1,2,3],
             start=0,goal=3,depth=4,work_budget=100_000)
    r.update(overrides)
    return r


def infer(ir, units, entry='Derive', **overrides):
    inputs = request(units)
    if entry == 'Derive':
        del inputs['work_budget']
        inputs['path_budget'] = 100
        inputs['depth'] = 3
    inputs.update(overrides)
    return execute(ir, inputs, entry)


def test_summary_matches_exhaustive_walks_and_proof_verifier(ir):
    rng = random.Random(20261031)
    for seed in range(24):
        units = [unit(str(i),rng.randrange(4),rng.randrange(4),
                      rng.choice(['VERIFIED','VERIFIED','UNKNOWN','HYPOTHESIS'])) for i in range(9)]
        trusted = [binding(u) for u in units]
        if seed % 3 == 0:
            units[0]['revoked'] = True
            trusted[1]['revision'] = 9
        if seed % 4 == 0:
            units[2]['polarity'] = -1
            trusted[2] = binding(units[2])
        for depth in (1,3,5):
            inputs = request(units,trusted=trusted,depth=depth,start=seed%4)
            summary = execute(ir,inputs)
            exhaustive = dict(inputs); del exhaustive['work_budget']; exhaustive['path_budget']=100_000
            expected = execute(ir,exhaustive,'Derive')
            assert summary['admitted'] == expected['admitted']
            assert summary['status'] == expected['status']
            assert set(summary['dependencies']) == set(expected['dependencies'])
            assert summary['proof_path'] == expected['proof_path']
            if summary['proof_path']:
                assert execute(ir,dict(units=units,trusted=trusted,start=inputs['start'],
                                       goal=3,path=summary['proof_path'],depth=depth),'VerifyProof')


def test_budget_boundary_discards_partial_conclusions(ir):
    inputs = request([unit('a',0,1),unit('b',1,3,'UNKNOWN')])
    r = execute(ir,inputs)
    assert r['status']=='HYPOTHESIS'
    assert execute(ir,dict(inputs,work_budget=r['work']))['admitted']
    stopped = execute(ir,dict(inputs,work_budget=r['work']-1))
    assert stopped['resource_limit'] and not stopped['admitted']
    assert stopped['status']=='UNKNOWN' and stopped['proof_path']==stopped['dependencies']==[]


def layered(width=8,layers=40):
    units=[]
    previous=[0]
    for layer in range(layers):
        current=[2+layer*width+i for i in range(width)]
        for a in previous:
            for b in current:
                units.append(unit(str(len(units)),a,b))
        previous=current
    for a in previous:
        units.append(unit(str(len(units)),a,1))
    return units


def test_exponentially_many_walks_use_linear_work(ir):
    units=layered()
    units[20]['semantic_status']='UNKNOWN'
    units.append(unit('irrelevant',9000,9001,'UNKNOWN'))
    inputs=request(units,entities=list(range(322)),goal=1,depth=41)
    r=execute(ir,inputs)
    assert r['admitted'] and r['status']=='VERIFIED'
    assert r['dependencies']==['20'] and len(r['proof_path'])==41
    assert r['work'] < 12*(len(units)+len(inputs['entities']))
    assert 'all_paths' not in r
    old=dict(inputs);del old['work_budget'];old['path_budget']=2000
    assert execute(ir,old,'Derive')['resource_limit']


@pytest.mark.parametrize('entry', ['Derive', 'Summarize'])
@pytest.mark.parametrize('mutation',[{'revoked':True},{'current_revision':2},{'provenance':[]},
                                    {'evidence':[]},{'negative_evidence':['negative']}])
def test_invalid_or_contradicted_edges_never_verify(ir,entry,mutation):
    u=unit('a',0,3);trusted=[binding(u)];u.update(mutation)
    assert infer(ir,[u],entry=entry,trusted=trusted)['status']=='UNKNOWN'


@pytest.mark.parametrize('entry', ['Derive', 'Summarize'])
def test_duplicate_ids_and_nonempty_cycles(ir,entry):
    u=unit('',0,0)
    assert infer(ir,[u],entry=entry,goal=0)['proof_path']==['']
    assert infer(ir,[],entry=entry,goal=0)['status']=='UNKNOWN'
    assert not infer(ir,[u,u],entry=entry,goal=0)['admitted']


def test_negative_evidence_binding_and_shared_identifiers(ir):
    units=[unit('a',0,3),unit('b',0,3)]
    for u in units:u['evidence']=['shared']
    trusted=[binding(u) for u in units];trusted[0]['subject']=5
    assert execute(ir,request(units,trusted=trusted))['proof_path']==['b']
    negative=unit('neg',0,3);negative['polarity']=-1
    assert execute(ir,request(units+[negative]))['status']=='CONTRADICTED'


def test_graph_result_fields_are_statically_accessible():
    validate(parse('''module Check {
 calculation Main {
  let x = graph.summarize([],[],[0],0,0,1,100)
  result = x.admitted && x.work >= 0
 }
}'''))


@pytest.mark.parametrize('depth,budget', [(0,100),(-1,100),(1,0),(1,100_000_001)])
def test_invalid_bounds_are_structured_diagnostics(ir,depth,budget):
    r=run_ir(ir,entry='UnifiedB::Summarize',inputs=request([],depth=depth,work_budget=budget))
    assert not r.ok and r.error_code=='GRAPH-004'


def test_native_field_types_are_checked_even_for_custom_structs():
    ir=lower_program(parse('''module Bad {
 struct Fake { unit_id: int }
 calculation Main {
  result = graph.summarize([Fake { unit_id: 7 }],[],[0,1],0,1,2,100)
 }
}'''))
    r=run_ir(ir)
    assert not r.ok and r.error_code=='GRAPH-003'


def test_stable_paths_unknown_dependencies_and_contradiction(ir):
    units = [unit("z", 0, 1), unit("b", 1, 3), unit("a", 0, 2),
             unit("c", 2, 3, "UNKNOWN")]
    r = infer(ir, units)
    assert r["status"] == "VERIFIED"
    assert r["proof_path"] == ["z", "b"]
    assert r["all_paths"] == [["z", "b"], ["a", "c"]]
    assert r["dependencies"] == ["c"]
    negative = unit("negative", 0, 3); negative["polarity"] = -1
    assert infer(ir, units + [negative])["status"] == "CONTRADICTED"


def test_path_budget_discards_partial_proof(ir):
    r = infer(ir, [unit("a", 0, 3), unit("b", 0, 3)], path_budget=1)
    assert r["resource_limit"] and not r["admitted"] and r["proof_path"] == []


@pytest.mark.parametrize("entry", ["Derive", "Summarize"])
@pytest.mark.parametrize("field,value", [("unit_id", "other"), ("subject", 8),
    ("predicate", 2), ("object", 8), ("polarity", -1), ("revision", 2)])
def test_evidence_cannot_be_rebound(ir, entry, field, value):
    u = unit("a", 0, 3); bad = binding(u); bad[field] = value
    assert infer(ir, [u], entry=entry, trusted=[bad])["status"] == "UNKNOWN"
    # Equal evidence IDs may legitimately have multiple bindings. Search the whole bucket.
    assert infer(ir, [u], entry=entry, trusted=[bad, binding(u)])["status"] == "VERIFIED"


def test_shared_evidence_id_does_not_scan_all_units(ir):
    units = [unit(str(i), i + 10, i + 11) for i in range(9_998)]
    units += [unit("start", 0, 1), unit("goal", 1, 3)]
    for u in units:
        u["evidence"] = ["shared-evidence"]
    r = infer(ir, units)
    assert r["admitted"] and r["status"] == "VERIFIED"
    assert r["proof_path"] == ["start", "goal"]
