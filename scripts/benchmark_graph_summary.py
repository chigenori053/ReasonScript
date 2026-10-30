#!/usr/bin/env python3
"""Measure large and exponentially branching inference with a native RSS watchdog."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import resource
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from frontend.language_surface import parse, validate
from frontend.computation_ir import lower_program
from frontend.computation_ir.optimizer import optimize_program


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def unit(uid,a,b,status='VERIFIED'):
    return dict(unit_id=uid,unit_kind='RU',semantic_status=status,state_representation='discrete',
                evidence=['shared'],dependencies=[],proof_path=[],revision=1,provenance=['scale-probe'],
                validation_status='NOT_VERIFIED',subject=a,object=b,predicate=1,polarity=1,
                current_revision=1,negative_evidence=[],revoked=False)

def fixture(family,size,seed):
    units=[]; depth=16
    if family=='branching':
        width=16; layers=128; previous=[0]; depth=layers+1
        for layer in range(layers):
            current=[2+layer*width+i for i in range(width)]
            for a in previous:
                for b in current:units.append(unit(str(len(units)),a,b))
            previous=current
        for a in previous:units.append(unit(str(len(units)),a,1))
        paths_log10=layers*math.log10(width)
    else:
        nodes=[0]+list(range(2,17))+[1]
        for a,b in zip(nodes,nodes[1:]):units.append(unit(str(len(units)),a,b))
        paths_log10=0
    unknown_id=units[seed % (16 if family=='branching' else len(units))]['unit_id']
    units[int(unknown_id)]['semantic_status']='UNKNOWN'
    while len(units)<size:
        i=len(units);units.append(unit(str(i),1_000_000+i,2_000_000+i))
    if len(units)!=size:raise ValueError('size is smaller than branching core')
    random.Random(seed).shuffle(units)
    trusted=[dict(evidence_id='shared',**{k:u[k] for k in ('unit_id','subject','predicate','object','polarity','revision')}) for u in units]
    inputs=dict(units=units,trusted=trusted,entities=list(range(2050)),start=0,goal=1,depth=depth,work_budget=100_000_000)
    expected=dict(status='VERIFIED' if family=='branching' else 'HYPOTHESIS',dependencies=[unknown_id],paths_log10=paths_log10)
    return inputs,expected


def worker(spec_path):
    spec=json.loads(Path(spec_path).read_text()); directory=Path(spec['directory'])
    output=directory/'response.json'; error=directory/'stderr.txt'
    start=time.monotonic(); sampled=0; limit=None
    with output.open('wb') as stdout,error.open('wb') as stderr:
        p=subprocess.Popen([spec['host'],spec['request']],stdout=stdout,stderr=stderr)
        try:
            while p.poll() is None:
                if time.monotonic()-start>spec['seconds']:limit='TIMEOUT';break
                memory=subprocess.run(['/bin/ps','-o','rss=','-p',str(p.pid)],capture_output=True,text=True,timeout=2)
                if memory.returncode==0 and memory.stdout.strip():
                    sampled=max(sampled,int(memory.stdout.strip())*1024)
                    if sampled>spec['rss_bytes']:limit='RSS_LIMIT';break
                elif memory.returncode and 'Operation not permitted' in memory.stderr:
                    limit='RSS_MONITOR_UNAVAILABLE';break
                time.sleep(0.05)
        finally:
            if p.poll() is None:p.kill()
            p.wait()
    peak=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
    if peak>spec['rss_bytes']:limit='RSS_LIMIT'
    response=json.loads(output.read_text()) if not limit and p.returncode==0 else None
    valid=False;value=None
    if response and response.get('ok'):
        value=next(iter(response['calculation_results'].values()))['fields']
        expected=spec['expected']
        valid=(value['admitted'] and not value['resource_limit'] and value['status']==expected['status']
               and sorted(value['dependencies'])==sorted(expected['dependencies']))
        # Independently validate the returned witness against original input records.
        inputs=json.loads(Path(spec['request']).read_text())['inputs']
        by_id={u['unit_id']:u for u in inputs['units']}
        bindings={tuple(b[k] for k in ('evidence_id','unit_id','subject','predicate','object','polarity','revision')) for b in inputs['trusted']}
        node=inputs['start'];proof=value['proof_path']
        if expected['status']=='VERIFIED':
            valid &= bool(proof) and len(proof)<=inputs['depth']
            for uid in proof:
                u=by_id.get(uid)
                if u is None:valid=False;break
                valid &= (u['subject']==node and u['predicate']==1 and u['polarity']==1
                          and u['semantic_status']=='VERIFIED' and not u['revoked']
                          and u['revision']==u['current_revision'] and bool(u['provenance'])
                          and bool(u['evidence']) and not u['negative_evidence'])
                valid &= all((e,uid,u['subject'],u['predicate'],u['object'],u['polarity'],u['revision']) in bindings for e in u['evidence'])
                node=u['object']
            valid &= node==inputs['goal']
        else:valid &= proof==[]
    print(json.dumps(dict(valid=bool(valid),seconds=time.monotonic()-start,limit=limit,exit_code=p.returncode,
                         sampled_peak_rss_bytes=sampled,peak_rss_bytes=peak,result=value,
                         diagnostics=response.get('diagnostics') if response else None)))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--sizes',nargs='+',type=int,default=[200_000,250_000])
    ap.add_argument('--seeds',nargs='+',type=int,default=[401,402,403])
    ap.add_argument('--repeats',type=int,default=1)
    ap.add_argument('--seconds',type=float,default=120)
    ap.add_argument('--rss-gib',type=float,default=4)
    ap.add_argument('--host',type=Path,default=ROOT/'ReasonRuntime/target/release/reason-runtime-host')
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    source=ROOT/'examples/inference_scale/main.rsn';ast=parse(source.read_text());validate(ast)
    ir=optimize_program(lower_program(ast));host=args.host.resolve(strict=True)
    environment=dict(host_sha256=sha(host),source_sha256=sha(source),seconds=args.seconds,rss_bytes=int(args.rss_gib*2**30),timing='Native process file parsing, ABI admission, graph summary, result serialization, and independent witness verification; source compilation and fixture generation excluded. Fresh process per repetition.')
    (args.out/'environment.json').write_text(json.dumps(environment,indent=2))
    failed=False
    with (args.out/'results.jsonl').open('x') as results:
        for family in ('sparse','branching'):
            for size in args.sizes:
                for seed in args.seeds:
                    inputs,expected=fixture(family,size,seed)
                    stem=f'{family}-{size}-{seed}';request=args.out/(stem+'-request.json')
                    request.write_text(json.dumps(dict(schema='reasonscript-runtime-request/1.0',request_id=stem,operation='execute',program=ir,
                        entry='UnifiedB::Summarize',inputs=inputs,context=dict(resource_root=str(ROOT),backend='RuntimeReal',numeric_mode='compat-reference',
                        capabilities=dict(filesystem_read=False,filesystem_write=False,network=False),limits=dict(max_input_elements=10_000_000,max_input_bytes=536870912,max_loop_iterations=10_000_000),
                        trace=dict(enabled=False),reasoning=dict(semantic_events=False),reason_units='off',executable_reason_units='off')),separators=(',',':')))
                    del inputs
                    request_hash=sha(request)
                    for repeat in range(args.repeats):
                        directory=args.out/f'{stem}-{repeat}';directory.mkdir()
                        spec=dict(directory=str(directory),host=str(host),request=str(request),expected=expected,seconds=args.seconds,rss_bytes=environment['rss_bytes'])
                        spec_path=directory/'spec.json';spec_path.write_text(json.dumps(spec))
                        run=subprocess.run([sys.executable,__file__,'worker',str(spec_path)],capture_output=True,text=True,timeout=args.seconds+90)
                        if run.returncode:raise RuntimeError(run.stderr)
                        row=json.loads(run.stdout);row.update(family=family,size=size,seed=seed,repeat=repeat,expected=expected,request_sha256=request_hash)
                        failed |= not row['valid'];results.write(json.dumps(row)+'\n');results.flush()
                        print(f"{stem} repeat={repeat}: {'PASS' if row['valid'] else 'FAIL'} {row['seconds']:.2f}s RSS={row['peak_rss_bytes']/2**30:.2f}GiB",flush=True)
    return int(failed)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='worker':worker(sys.argv[2])
    else:raise SystemExit(main())
