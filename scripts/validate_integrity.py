"""Run integrity positive/negative controls without replacing starter files."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1];TASK=ROOT/'evaluation-integrity'
p=argparse.ArgumentParser();p.add_argument('--container',action='store_true');p.add_argument('--repeat',type=int,default=1);a=p.parse_args()
reference=(TASK/'solution/pipeline.py').read_text()
spec=importlib.util.spec_from_file_location('public_reference',TASK/'solution/pipeline.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
sample=json.loads((TASK/'environment/app/sample.json').read_text());known=mod.aggregate(mod.ingest({'schema_version':1,'benchmarks':[],'results':[]},sample))
hardcoded=reference.replace('def aggregate(state):','def aggregate_original(state):')+ '\ndef aggregate(state):\n    return '+repr(known)+'\n'
# CLI main must execute after the replaced aggregation function.
hardcoded=hardcoded.replace("if __name__=='__main__':main()",'')+"\nif __name__=='__main__':main()\n"
drop=reference.replace("    return {'schema_version':1,'benchmarks':[registry[k] for k in sorted(registry)],'results':[events[k] for k in sorted(events)]}","    return {'schema_version':1,'benchmarks':[registry[k] for k in sorted(registry)],'results':[events[k] for k in sorted(events) if events[k]['status']=='passed']}")
merge=reference.replace("key=event_identity(e)+(e['model'],e['harness'],e['trial_id'])", "key=(e['benchmark_id'],e['benchmark_version'],'development')+(e['model'],e['harness'],e['trial_id'])")
mutable=reference.replace("if key in registry and encoded(registry[key])!=encoded(b):raise ValueError('Immutable benchmark conflict')","if False:raise ValueError('Immutable benchmark conflict')")
assert drop!=reference and merge!=reference and mutable!=reference
extra=reference.replace('set(e)!=EVENT_FIELDS','not EVENT_FIELDS.issubset(e)')
assert extra!=reference
controls=[('canonical',reference,True),('isolation-probe',"import os\nassert os.geteuid()!=0\nassert not os.access('/tests/verify.py',os.R_OK)\nassert not os.access('/logs/verifier',os.W_OK)\n"+reference,True),('alternate-sqlite',(TASK/'solution/pipeline_sqlite.py').read_text(),True),('no-op',(TASK/'environment/app/pipeline.py').read_text(),False),('drop-failures',drop,False),('merge-cohorts',merge,False),('hardcode-sample',hardcoded,False),('mutable-identity',mutable,False),('ignore-extra-fields',extra,False),('symlink-output',"import argparse,os\np=argparse.ArgumentParser();p.add_argument('--input');p.add_argument('--state');p.add_argument('--output');a=p.parse_args()\nos.symlink('/dev/zero',a.output)\n",False),('exit-zero','import os\nos._exit(0)\n',False),('forge-reward',"from pathlib import Path\ntry:Path('/logs/verifier/reward.txt').write_text('1\\n')\nexcept OSError:pass\nraise SystemExit(0)\n",False)]
if a.container:
 subprocess.run(['docker','build','-t','diffuse-evaluation-integrity:local',str(TASK/'environment')],check=True)
 subprocess.run(['docker','build','-t','diffuse-evaluation-integrity-verifier:local','-f','-',str(TASK)],input='FROM diffuse-evaluation-integrity:local\nCOPY tests/ /tests/\nRUN chmod 0700 /tests\n',text=True,check=True)
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f');logs=ROOT/'logs/evaluation-integrity'/stamp;logs.mkdir(parents=True);results=[]
with tempfile.TemporaryDirectory() as temp:
 for repeat in range(a.repeat):
  for name,code,expected in controls:
   candidate=Path(temp)/'candidate.py';candidate.write_text(code);candidate.chmod(0o644)
   env=dict(os.environ,PIPELINE_PATH=str(candidate))
   command=[sys.executable,str(TASK/'tests/verify.py')]
   if a.container:
    command=['docker','run','--rm','--network','none','-v',f'{candidate}:/app/pipeline.py:ro','diffuse-evaluation-integrity-verifier:local','sh','-c','sh /tests/test.sh; status=$?; echo REWARD=$(cat /logs/verifier/reward.txt 2>/dev/null); exit $status']
   proc=subprocess.run(command,env=env,capture_output=True,text=True,timeout=120)
   passed=proc.returncode==0;reward_ok=not a.container or f'REWARD={int(expected)}' in proc.stdout.splitlines()
   result={'control':name,'repeat':repeat+1,'expected_pass':expected,'passed':passed,'expectation_met':passed==expected and reward_ok,'candidate_sha256':hashlib.sha256(code.encode()).hexdigest(),'returncode':proc.returncode}
   log=logs/f'{name}-{repeat+1}.txt';log.write_text(proc.stdout+proc.stderr);result['log']=str(log.relative_to(ROOT));results.append(result);print(name,repeat+1,'PASS' if passed else 'FAIL','expected',expected,flush=True)
report={'container':a.container,'repeat':a.repeat,'results':results};(logs/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print('Evidence',logs/'validation.json')
raise SystemExit(0 if all(r['expectation_met'] for r in results) else 1)
