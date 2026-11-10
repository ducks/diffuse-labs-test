"""Deterministic regression checks for observed harness disk failures."""
import importlib.util
from pathlib import Path
import unittest
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('infra',root/'terraform-k8s/tests/infrastructure.py')
infra=importlib.util.module_from_spec(spec);spec.loader.exec_module(infra)

class Infrastructure(unittest.TestCase):
    def test_observed_root_block_errors(self):
        for line in ['cluster # [25.3] I/O error, dev vda, sector 6397952 op 0x1:(WRITE)', 'cluster # Buffer I/O error on device vda, logical block 800768']:
            self.assertTrue(infra.root_disk_failure(line))
    def test_application_errors_remain_evaluated(self):
        for line in ['permission denied /var/lib/postgresql/data', 'Timed out: API readiness', 'I/O error, dev vdb, sector 3', 'Remounting / read-only', 'test succeeded']:
            self.assertFalse(infra.root_disk_failure(line))
    def test_infrastructure_is_detected_alongside_application_failure(self):
        text='cluster # I/O error, dev vda, sector 6397952\nTERRAFORM_K8S_SPIKE_FAILED {"passed":false,"error":"API readiness"}'
        self.assertTrue(infra.root_disk_failure(text))

if __name__=='__main__':unittest.main()
