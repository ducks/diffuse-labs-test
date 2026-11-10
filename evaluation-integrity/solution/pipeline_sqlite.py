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
    import sqlite3
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE attempts (b TEXT,v TEXT,c TEXT,m TEXT,h TEXT,t TEXT,a INTEGER,s TEXT)')
        db.executemany('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?)',[(e['benchmark_id'],e['benchmark_version'],e['cohort'],e['model'],e['harness'],e['trial_id'],e['attempt'],e['status']) for e in state['results']])
        rows=db.execute('WITH ranked AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY b,v,c,m,h,t ORDER BY a DESC) AS rank FROM attempts) SELECT b,v,c,m,h,s,COUNT(*) FROM ranked WHERE rank=1 GROUP BY b,v,c,m,h,s ORDER BY b,v,c,m,h,s').fetchall()
    definitions={identity(b):b for b in state['benchmarks']};groups={}
    for b,v,c,m,h,status,count in rows:
        key=(b,v,c,m,h)
        if key not in groups:
            manifest=definitions[(b,v,c)]['manifest']
            fingerprint=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
            groups[key]={'benchmark_id':b,'benchmark_version':v,'cohort':c,'manifest_sha256':fingerprint,'model':m,'harness':h,'trials':0,**{s:0 for s in STATUSES}}
        groups[key][status]=count;groups[key]['trials']+=count
    for g in groups.values():
        g['evaluated']=sum(g[s] for s in STATUSES[:3]);g['pass_rate']=g['passed']/g['evaluated'] if g['evaluated'] else None
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
