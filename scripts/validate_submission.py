"""Repeat clean controls and Harbor trials; preserve logs and reward evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
TASKS=['session-recovery','streaming-gateway','dataset-containment','terraform-k8s','evaluation-integrity']
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--phase',choices=['all','controls','harbor'],default='all')
parser.add_argument('--rounds',type=int,default=2)
args=parser.parse_args()
if not 1<=args.rounds<=3:parser.error('--rounds must be between 1 and 3')
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
output=ROOT/'logs/submission-validation'/stamp;output.mkdir(parents=True)
records=[]

def run(label,command,evidence=None):
    log=output/(label+'.log')
    with log.open('w') as stream:
        try:
            proc=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=10800)
            code=proc.returncode
        except subprocess.TimeoutExpired:
            code=None
    record={'label':label,'command':command,'exit_code':code,'log':str(log.relative_to(ROOT)), 'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()}
    if evidence and evidence.exists():
        copy=output/(label+'.json');copy.write_bytes(evidence.read_bytes());record['evidence']=str(copy.relative_to(ROOT))
    records.append(record);(output/'summary.json').write_text(json.dumps(records,indent=2)+'\n')
    print(label,'exit',code,flush=True)
    if code!=0:raise SystemExit('Validation did not succeed; inspect '+str(log))

print('Evidence:',output,flush=True)
run('terraform-infrastructure-classification',['python','scripts/test_terraform_infrastructure.py'])
if args.phase in ['all','controls']:
    for index in range(1,args.rounds+1):
        for task,script in [('session-recovery','validate.py'),('streaming-gateway','validate_gateway.py'),('dataset-containment','validate_containment.py')]:
            summary=ROOT/'logs'/('validation-container.json' if task=='session-recovery' else task+'/validation-container.json')
            run(f'{task}-controls-{index}',['python','scripts/'+script,'--container'],summary)
        run(f'terraform-controls-{index}',['python','scripts/validate_terraform.py'])
    run('integrity-controls',['python','scripts/validate_integrity.py','--container','--repeat',str(args.rounds)])
if args.phase in ['all','harbor']:
    run('prepare-terraform-image',['python','scripts/prepare_terraform_harbor.py'])
    for index in range(1,args.rounds+1):
        for task in TASKS:
            summary=ROOT/'logs'/('validation-harbor.json' if task=='session-recovery' else task+'/validation-harbor.json')
            run(f'{task}-harbor-{index}',['python','scripts/validate_harbor.py','--task',task],summary)
print('All requested checks succeeded. Evidence:',output,flush=True)
