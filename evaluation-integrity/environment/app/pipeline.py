"""Legacy comparison importer: investigate the misleading improvement report."""
import argparse
import hashlib
import json
from pathlib import Path

def run(batch,state):
    # Last import wins: some manifests were edited in place by developers.
    registry={b['id']:b for b in state['benchmarks']}
    registry.update({b['id']:b for b in batch['benchmarks']})
    events={e['event_id']:e for e in state['results']}
    events.update({e['event_id']:e for e in batch['results']})
    groups={}
    for e in events.values():
        # Dashboard originally grouped only by model and ignored interruptions.
        if e['status'] not in ('passed','failed'):continue
        key=e['model'];b=registry[e['benchmark_id']]
        g=groups.setdefault(key,{'benchmark_id':b['id'],'benchmark_version':b['version'],'cohort':b['cohort'],'manifest_sha256':hashlib.sha256(json.dumps(b['manifest']).encode()).hexdigest(),'model':key,'harness':e['harness'],'trials':0,'passed':0,'failed':0,'interrupted':0,'unavailable':0})
        g['trials']+=1;g[e['status']]+=1
    for g in groups.values():g['evaluated']=g['trials'];g['pass_rate']=g['passed']/g['evaluated']
    return {'schema_version':1,'benchmarks':list(registry.values()),'results':list(events.values())},{'schema_version':1,'groups':list(groups.values())}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    state=json.loads(a.state.read_text()) if a.state.exists() else {'schema_version':1,'benchmarks':[],'results':[]}
    state,report=run(json.loads(a.input.read_text()),state)
    a.state.write_text(json.dumps(state)+'\n');a.output.write_text(json.dumps(report)+'\n')
