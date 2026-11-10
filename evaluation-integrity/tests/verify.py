"""Trusted black-box checks. Candidate runs as nobody with no protected fixtures."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import signal
import subprocess
import sys
import tempfile
import unittest


def wire(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n'


def fixtures(seed):
    rng=random.Random(seed);benchmarks=[];events=[]
    for version in ['old-'+str(seed),'new-'+str(seed)]:
        for cohort in ['development','held-out']:
            b={'id':'suite-λ-'+str(seed),'version':version,'cohort':cohort,'manifest':{'cases':['dns','disk','queue'],'release':version,'seed':seed,'boundary':cohort,'settings':{'enabled':True,'retries':1}}}
            benchmarks.append(b)
            for model in ['swift-'+str(seed),'careful-'+str(seed)]:
                for harness in ['native-a','adapter-b']:
                    for trial in range(4):
                        for attempt in range(1,rng.randrange(2,5)):
                            e={'event_id':f'{seed}-{len(events):04d}','trial_id':f'trial-{trial}','benchmark_id':b['id'],'benchmark_version':version,'cohort':cohort,'model':model,'harness':harness,'attempt':attempt,'status':rng.choice(['passed','failed','interrupted','unavailable'])}
                            events.append(e)
                            if rng.randrange(3)==0:events.append({**e,'event_id':f'{seed}-{len(events):04d}'})
    # Preserve an unused historical benchmark, too.
    benchmarks.append({'id':'retired-'+str(seed),'version':'0','cohort':'held-out','manifest':{'retired':True}})
    return {'benchmarks':benchmarks,'results':events}


def expected(batch):
    """Independent, group-first scan; no code imported from any submission/solution."""
    groups=[]
    for b in sorted(batch['benchmarks'],key=lambda b:(b['id'],b['version'],b['cohort'])):
        relevant=[e for e in batch['results'] if (e['benchmark_id'],e['benchmark_version'],e['cohort'])==(b['id'],b['version'],b['cohort'])]
        for model,harness in sorted({(e['model'],e['harness']) for e in relevant}):
            rows=[e for e in relevant if (e['model'],e['harness'])==(model,harness)]
            counts={s:0 for s in ['passed','failed','interrupted','unavailable']}
            trials=sorted({e['trial_id'] for e in rows})
            for trial in trials:
                attempts=[e for e in rows if e['trial_id']==trial];latest=max(e['attempt'] for e in attempts)
                statuses={e['status'] for e in attempts if e['attempt']==latest};assert len(statuses)==1
                counts[statuses.pop()]+=1
            denominator=sum(counts[s] for s in ['passed','failed','interrupted'])
            manifest=json.dumps(b['manifest'],ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
            groups.append({'benchmark_id':b['id'],'benchmark_version':b['version'],'cohort':b['cohort'],'manifest_sha256':hashlib.sha256(manifest.encode()).hexdigest(),'model':model,'harness':harness,'trials':len(trials),**counts,'evaluated':denominator,'pass_rate':counts['passed']/denominator if denominator else None})
    return {'schema_version':1,'groups':groups}


def expected_state(batch):
    return {'schema_version':1,'benchmarks':sorted(batch['benchmarks'],key=lambda b:(b['id'],b['version'],b['cohort'])),'results':sorted({e['event_id']:e for e in batch['results']}.values(),key=lambda e:e['event_id'])}


def restrict():
    resource.setrlimit(resource.RLIMIT_CPU,(3,3))
    resource.setrlimit(resource.RLIMIT_FSIZE,(4*1024*1024,4*1024*1024))
    resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
    resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
    if os.geteuid()==0:
        os.setgroups([]);os.setgid(65534);os.setuid(65534)


CANDIDATE=Path(os.environ.get('PIPELINE_PATH','/app/pipeline.py'))

class Integrity(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='integrity-case-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o711)
        self.inputs=self.root/'inputs';self.inputs.mkdir(mode=0o755)
        self.work=self.root/'work';self.work.mkdir(mode=0o700)
        if os.geteuid()==0:os.chown(self.work,65534,65534)
        self.candidate=self.work/'pipeline.py';self.candidate.write_bytes(CANDIDATE.read_bytes());self.candidate.chmod(0o444)
        self.state=self.work/'ledger.json';self.output=self.work/'report.json';self.counter=0

    def run_batch(self,batch,valid=True):
        self.counter+=1;source=self.inputs/f'input-{self.counter}.json';source.write_text(wire(batch));source.chmod(0o444)
        command=[sys.executable,str(self.candidate),'--input',str(source),'--state',str(self.state),'--output',str(self.output)]
        before=source.read_bytes()
        with tempfile.TemporaryFile() as stdout,tempfile.TemporaryFile() as stderr:
            proc=subprocess.Popen(command,cwd=self.work,env={'PATH':'/usr/local/bin:/usr/bin:/bin','PYTHONHASHSEED':'0'},stdout=stdout,stderr=stderr,start_new_session=True,preexec_fn=restrict)
            try:status=proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait();self.fail('Candidate timed out')
            finally:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            stderr.seek(0);detail=stderr.read(2000).decode(errors='replace')
        self.assertEqual(source.read_bytes(),before,'Input was modified')
        if valid:self.assertEqual(status,0,detail)
        else:self.assertNotEqual(status,0,'Invalid import was accepted')
        for artifact in [self.state,self.output]:
            if artifact.exists() or artifact.is_symlink():
                self.assertFalse(artifact.is_symlink(),'Output artifacts must not be symlinks')
                self.assertTrue(artifact.is_file(),'Output artifacts must be regular files')
                self.assertLessEqual(artifact.stat().st_size,4*1024*1024,'Output artifact too large')
        if valid:
            self.assertTrue(self.state.is_file() and self.output.is_file(),'Missing state/report')
            return json.loads(self.output.read_text())

    def check_all(self,batch):
        self.assertEqual(self.run_batch(batch),expected(batch))
        self.assertEqual(self.state.read_text(),wire(expected_state(batch)),'History missing or nondeterministic')
        self.assertEqual(self.output.read_text(),wire(expected(batch)))

    def test_unseen_datasets_cohorts_attribution_and_history(self):
        for seed in [103,809,20261109]:
            with self.subTest(seed=seed):
                batch=fixtures(seed)
                self.state.unlink(missing_ok=True);self.check_all(batch)

    def test_known_boundary_counts(self):
        batch=fixtures(47);b=batch['benchmarks'][0];base={'benchmark_id':b['id'],'benchmark_version':b['version'],'cohort':b['cohort'],'model':'boundary','harness':'h1'}
        batch['results']=[{**base,'event_id':str(i),'trial_id':str(i),'attempt':1,'status':s} for i,s in enumerate(['passed','failed','interrupted','unavailable'])]
        report=self.run_batch(batch);g=report['groups'][0]
        self.assertEqual((g['trials'],g['evaluated'],g['passed'],g['failed'],g['interrupted'],g['unavailable'],g['pass_rate']),(4,3,1,1,1,1,1/3))
        batch['results']=[{**batch['results'][-1],'event_id':'only'}];self.state.unlink();g=self.run_batch(batch)['groups'][0];self.assertIsNone(g['pass_rate']);self.assertEqual(g['evaluated'],0)

    def test_retries_latest_interruption_and_exact_duplicate(self):
        batch=fixtures(61);e=batch['results'][0];batch['results']=[{**e,'event_id':'first','status':'passed','attempt':1},{**e,'event_id':'last','status':'interrupted','attempt':2}]
        batch['results']+=[copy.deepcopy(batch['results'][0]),{**batch['results'][-1],'event_id':'delivery-retry'}]
        self.check_all(batch);g=json.loads(self.output.read_text())['groups'][0]
        self.assertEqual((g['trials'],g['interrupted'],g['pass_rate']),(1,1,0))

    def test_reordering_incremental_ingestion_and_idempotency(self):
        batch=fixtures(911);self.check_all(batch);state=self.state.read_bytes();output=self.output.read_bytes()
        shuffled=copy.deepcopy(batch);random.Random(18).shuffle(shuffled['results']);shuffled['benchmarks'].reverse()
        self.state.unlink();self.check_all(shuffled);self.assertEqual(self.state.read_bytes(),state);self.assertEqual(self.output.read_bytes(),output)
        self.state.unlink();self.run_batch({'benchmarks':batch['benchmarks'],'results':[]})
        for offset in range(0,len(shuffled['results']),23):self.run_batch({'benchmarks':[],'results':shuffled['results'][offset:offset+23]})
        self.assertEqual(self.state.read_bytes(),state);self.assertEqual(self.output.read_bytes(),output)
        self.run_batch(shuffled);self.assertEqual(self.state.read_bytes(),state);self.assertEqual(self.output.read_bytes(),output)

    def test_invalid_batch_leaves_ledger_and_report_unchanged(self):
        batch=fixtures(73);self.check_all(batch);state=self.state.read_bytes();report=self.output.read_bytes();e=batch['results'][0]
        numeric=copy.deepcopy(batch['benchmarks'][0]);numeric['manifest']['seed']=float(numeric['manifest']['seed'])
        boolean=copy.deepcopy(batch['benchmarks'][0]);boolean['manifest']['settings']['enabled']=1
        bad_batches=[{'benchmarks':[],'results':[{**e,'event_id':'extra-event','trial_id':'extra-trial','extra':'not-in-contract'}]},{'benchmarks':[{**batch['benchmarks'][0],'extra':True}],'results':[]},{'benchmarks':[],'results':[{**e,'model':''}]},{'benchmarks':[],'results':[{**e,'harness':42}]},{'benchmarks':[],'results':[{k:v for k,v in e.items() if k!='trial_id'}]},{'benchmarks':[numeric],'results':[]},{'benchmarks':[boolean],'results':[]},{'benchmarks':[{**batch['benchmarks'][0],'manifest':{'changed':True}}],'results':[]},
            {'benchmarks':[],'results':[{**e,'status':'unknown'}]},
            {'benchmarks':[],'results':[{**e,'status':'failed' if e['status']!='failed' else 'passed'}]},
            {'benchmarks':[],'results':[{**e,'event_id':'conflict-delivery','status':'failed' if e['status']!='failed' else 'passed'}]},
            {'benchmarks':[],'results':[{**e,'event_id':'orphan','benchmark_version':'missing'}]},
            {'benchmarks':[],'results':[{**e,'event_id':'bool','attempt':True}]}]
        for bad in bad_batches:
            # Include a valid new event first; no partial import may survive.
            bad=copy.deepcopy(bad);bad['results'].insert(0,{**e,'event_id':'must-rollback','attempt':100})
            with self.subTest(bad=bad):
                self.run_batch(bad,valid=False);self.assertEqual(self.state.read_bytes(),state);self.assertEqual(self.output.read_bytes(),report)


def main():
    if os.environ.get('REQUIRE_ISOLATION')=='1' and os.geteuid()!=0:raise RuntimeError('Container root required to isolate candidate UID')
    if not CANDIDATE.is_file() or CANDIDATE.is_symlink() or CANDIDATE.stat().st_size>256*1024:
        print('Invalid collected submission');return False
    return unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Integrity)).wasSuccessful()

if __name__=='__main__':
    passed=main()
    if os.environ.get('REQUIRE_ISOLATION')=='1':
        Path('/logs/verifier/reward.txt').write_text('1\n' if passed else '0\n')
        # Graded failures publish reward 0. Infrastructure exceptions publish none.
    raise SystemExit(0 if passed else 1)
