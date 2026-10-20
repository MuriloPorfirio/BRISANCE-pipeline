"""Opt-in real Nextflow config test with MOCK disk/GPU and trivial task scripts.

Set BRISANCE_TEST_NF to a local 26.04.6 executable. No Docker, real GPU or
sequencing data is used. This does not test Parabricks or WGS performance.
"""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


WORKFLOW = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('full_nf_integration', WORKFLOW / 'hg008_full_run.py')
FULL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FULL)


@unittest.skipUnless(os.environ.get('BRISANCE_TEST_NF'), 'Opt-in: requires a local Nextflow executable')
class NextflowSafetyIntegration(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='brisance-safety-nf-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.nf = os.environ['BRISANCE_TEST_NF']
        self.bin = self.root / 'fakebin'
        self.bin.mkdir()
        gpu = self.bin / 'nvidia-smi'
        gpu.write_text('''#!/usr/bin/env python3
import os,sys
if any('query-compute-apps' in arg for arg in sys.argv):
    raise SystemExit(0)
for index in ('5','6','7'):
    print('{}, GPU-{}, NVIDIA A100-SXM4-80GB, 81920, 81050, {}'.format(index,index,os.environ.get('MOCK_GPU_UTIL','0')))
''')
        gpu.chmod(0o755)
        wrapper = self.root / 'fixture_guard.py'
        wrapper.write_text('''import importlib.util,sys
spec=importlib.util.spec_from_file_location('full', %r)
full=importlib.util.module_from_spec(spec)
spec.loader.exec_module(full)
# Explicitly mock disk only. The original stage guard and GPU parser execute.
full.storage=lambda: {'used_fraction': .4}
sys.exit(full.main())
''' % str(WORKFLOW / 'hg008_full_run.py'))
        self.safety = self.root / 'safety.config'
        with patch.object(FULL, '__file__', str(wrapper)):
            FULL.guard_config(self.safety)
        config = self.root / 'nextflow.config'
        config.write_text('''includeConfig %r
includeConfig %r
docker.enabled = false
process {
    withName: TRIM_GALORE { cpus = 1; memory = '1 MB' }
    withName: FQ2BAM { cpus = 1; memory = '1 MB' }
}
''' % (str(WORKFLOW / 'nextflow.config'), str(self.safety)))
        (self.root / 'fixture.nf').write_text('''process TRIM_GALORE {
    container 'MOCK_NEVER_PULLED'
    output:
    path 'trim.mock'
    script:
    "printf 'MOCK_NOT_BIOLOGICAL' > trim.mock"
}
process FQ2BAM {
    container 'MOCK_NEVER_PULLED'
    input:
    path trimmed
    output:
    path 'aligned.mock'
    script:
    "printf 'MOCK_NOT_BIOLOGICAL' > aligned.mock"
}
workflow {
    TRIM_GALORE()
    FQ2BAM(TRIM_GALORE.out)
}
''')
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        NXF_HOME=str(self.root / 'nxf-home'))

    def run_fixture(self, **environment):
        return subprocess.run([self.nf, '-log', str(self.root / 'nextflow.log'),
            'run', str(self.root / 'fixture.nf'), '-work-dir', str(self.root / 'work'),
            '-with-trace', str(self.root / 'trace.tsv'), '-ansi-log', 'false'],
            cwd=self.root, env=dict(self.env, **environment), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)

    def test_guard_config_merges_with_resource_config_and_runs_on_host(self):
        result = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(len(list((self.root / 'work').rglob('aligned.mock'))), 1)
        # Nextflow places beforeScript in the host wrapper, not task payload.
        commands = list((self.root / 'work').rglob('.command.run'))
        self.assertEqual(len(commands), 2)
        self.assertTrue(all('--stage-guard' in command.read_text() for command in commands))
        self.assertTrue(all('COMPLETED' in row for row in (self.root / 'trace.tsv').read_text().splitlines()[1:]))

    def test_busy_gpu_guard_prevents_task_payload(self):
        result = self.run_fixture(MOCK_GPU_UTIL='65')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('GPU 5 ocupada', result.stdout)
        self.assertEqual(len(list((self.root / 'work').rglob('aligned.mock'))), 0)


if __name__ == '__main__':
    unittest.main()
