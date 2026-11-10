"""Immutable event ingestion with logical-trial retry accounting."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

BENCHMARK_FIELDS = {'id','version','cohort','manifest'}
EVENT_FIELDS = {'event_id','trial_id','model','harness','benchmark_id','benchmark_version','cohort','attempt','status'}
STATUSES = ('passed','failed','interrupted','unavailable')

def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n'

def identity(b):
    return b['id'],b['version'],b['cohort']

def event_identity(e):
    return e['benchmark_id'],e['benchmark_version'],e['cohort']

def nonempty(value):
    return isinstance(value,str) and bool(value)

def validate_benchmark(b):
    if not isinstance(b,dict) or set(b)!=BENCHMARK_FIELDS:raise ValueError('Invalid benchmark fields')
    if not all(nonempty(b[k]) for k in ['id','version']):raise ValueError('Invalid benchmark identity')
    if b['cohort'] not in ('development','held-out') or not isinstance(b['manifest'],dict):raise ValueError('Invalid benchmark definition')
    encoded(b)

def validate_event(e):
    if not isinstance(e,dict) or set(e)!=EVENT_FIELDS:raise ValueError('Invalid event fields')
    if not all(nonempty(e[k]) for k in EVENT_FIELDS-{'attempt','status'}):raise ValueError('Invalid result identity')
    if type(e['attempt']) is not int or e['attempt']<1 or e['status'] not in STATUSES:raise ValueError('Invalid attempt/status')

def ingest(state,batch):
    if not isinstance(state,dict) or set(state)!={'schema_version','benchmarks','results'} or type(state['schema_version']) is not int or state['schema_version']!=1:raise ValueError('Invalid ledger schema')
    if not isinstance(batch,dict) or set(batch)!={'benchmarks','results'}:raise ValueError('Invalid batch schema')
    for source in [state,batch]:
        if not isinstance(source['benchmarks'],list) or not isinstance(source['results'],list):raise ValueError('Invalid arrays')
    registry={}
    for b in state['benchmarks']+batch['benchmarks']:
        validate_benchmark(b);key=identity(b)
        if key in registry and encoded(registry[key])!=encoded(b):raise ValueError('Immutable benchmark conflict')
        registry[key]=b
    events={};attempts={}
    for e in state['results']+batch['results']:
        validate_event(e)
        if event_identity(e) not in registry:raise ValueError('Unknown benchmark')
        key=e['event_id']
        if key in events and events[key]!=e:raise ValueError('Event ID conflict')
        events[key]=e
        attempt=event_identity(e)+(e['model'],e['harness'],e['trial_id'],e['attempt'])
        payload={k:v for k,v in e.items() if k!='event_id'}
        if attempt in attempts and attempts[attempt]!=payload:raise ValueError('Attempt conflict')
        attempts[attempt]=payload
    return {'schema_version':1,'benchmarks':[registry[k] for k in sorted(registry)],'results':[events[k] for k in sorted(events)]}

def aggregate(state):
    registry={identity(b):b for b in state['benchmarks']}
    latest={}
    for e in state['results']:
        key=event_identity(e)+(e['model'],e['harness'],e['trial_id'])
        if key not in latest or latest[key]['attempt']<e['attempt']:latest[key]=e
    groups={}
    for key,e in latest.items():
        group=key[:-1]
        if group not in groups:
            b=registry[group[:3]]
            digest=hashlib.sha256(encoded(b['manifest']).rstrip('\n').encode()).hexdigest()
            groups[group]={'benchmark_id':group[0],'benchmark_version':group[1],'cohort':group[2],'manifest_sha256':digest,'model':group[3],'harness':group[4],**{s:0 for s in STATUSES},'trials':0}
        groups[group][e['status']]+=1;groups[group]['trials']+=1
    for g in groups.values():
        g['evaluated']=g['passed']+g['failed']+g['interrupted']
        g['pass_rate']=g['passed']/g['evaluated'] if g['evaluated'] else None
    return {'schema_version':1,'groups':[groups[k] for k in sorted(groups)]}

def replace_file(path,text):
    fd,name=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(text);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True,type=Path);parser.add_argument('--state',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    try:
        if len({p.resolve() for p in [args.input,args.state,args.output]})!=3:raise ValueError('Paths must be distinct')
        state=json.loads(args.state.read_text()) if args.state.exists() else {'schema_version':1,'benchmarks':[],'results':[]}
        updated=ingest(state,json.loads(args.input.read_text()))
        state_text=encoded(updated);report_text=encoded(aggregate(updated))
        replace_file(args.state,state_text);replace_file(args.output,report_text)
    except (ValueError,KeyError,TypeError,OSError) as error:
        parser.exit(2,str(error)+'\n')

if __name__=='__main__':main()
