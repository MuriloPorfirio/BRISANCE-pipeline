"""Launcher tests with fake Conda/Java/Nextflow, never real sequencing jobs."""

import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'run_hg008_20pct.sh'
DATASET = 'hg008-20pct-m_8ryr9u'


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='brisance-launcher-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        workflow = self.root / 'workflow'
        workflow.mkdir()
        self.script = workflow / SOURCE.name
        shutil.copy2(SOURCE, self.script)
        (workflow / 'main.nf').write_text('// MOCK_NOT_BIOLOGICAL\n')
        self.fake_env = self.root / 'fake-conda'
        (self.fake_env / 'lib/jvm/bin').mkdir(parents=True)
        (self.fake_env / 'bin').mkdir()
        java = self.fake_env / 'lib/jvm/bin/java'
        java.write_text('#!/bin/sh\nprintf "openjdk version \\"21.0.10\\"\\n" >&2\n')
        java.chmod(0o755)
        (self.fake_env / 'bin/java').symlink_to(java)
        self.conda = self.root / 'conda.sh'
        self.conda.write_text(
            'conda() {\n'
            '  [[ "$1" == activate && "$2" == brisance-nextflow ]] || return 1\n'
            f'  export CONDA_PREFIX={shlex.quote(str(self.fake_env))}\n'
            '}\n')
        self.nf = self.root / 'nextflow-26.04.6-dist'
        self.nf.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
home = Path(os.environ['CONDA_PREFIX']) / 'lib/jvm'
assert os.environ['NXF_JAVA_HOME'] == str(home)
assert os.environ['JAVA_HOME'] == str(home)
assert os.environ['JAVA_CMD'] == str(home / 'bin/java')
if args == ['-version']:
    print('MOCK Nextflow 26.04.6; NOT a real pipeline execution')
else:
    Path('captured-command.json').write_text(json.dumps(args))
    assert args[args.index('--mode') + 1] == 'finalize'
    assert '-resume' not in args
    assert args[args.index('--gpu_devices') + 1] == '7,6,5'
    assert args[args.index('--caller_gpu_devices') + 1] == '7,6'
    Path(args[args.index('--outdir') + 1]).mkdir(parents=True)
    Path(args[args.index('-work-dir') + 1]).mkdir(parents=True)
    print('MOCK_ONLY: tool outputs/CPU/GPU/data have NOT been tested')
    sys.exit(int(os.environ.get('MOCK_NF_EXIT', '0')))
''')
        self.nf.chmod(0o755)
        inputs = self.root / 'data/subsample' / DATASET
        inputs.mkdir(parents=True)
        (inputs / 'samplesheet.csv').write_text('MOCK CSV, not real FASTQs\n')
        (inputs / 'manifest.json').write_text('{"status":"complete","MOCK":true}\n')
        self.env = dict(os.environ, BRISANCE_CONDA_SH=str(self.conda), STY='MOCK-screen',
                        JAVA_CMD='/usr/bin/java', JAVA_HOME='', NXF_JAVA_HOME='/wrong-old-java')

    def run_script(self, *args, **env):
        return subprocess.run(['/bin/bash', str(self.script), *args], cwd='/tmp',
            env=dict(self.env, **env), text=True, capture_output=True, timeout=20)

    def test_check_overrides_stale_java_without_starting_processing(self):
        result = self.run_script('--check', STY='')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.fake_env / 'lib/jvm/bin/java'), result.stdout)
        self.assertIn('nenhum processamento', result.stdout)
        self.assertFalse((self.root / 'results').exists())
        self.assertFalse((self.root / 'reports').exists())
        self.assertFalse((self.root / 'captured-command.json').exists())

    def test_full_command_new_report_archive_and_exit_zero(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads((self.root / 'captured-command.json').read_text())
        self.assertEqual(args[args.index('--input') + 1], f'data/subsample/{DATASET}/samplesheet.csv')
        reports = list((self.root / 'reports' / DATASET).glob('execution-*'))
        self.assertEqual(len(reports), 1)
        self.assertTrue((reports[0] / 'console.log').is_file())
        self.assertTrue((reports[0] / 'nextflow.sha256').is_file())
        with tarfile.open(reports[0] / 'execution-inputs.tar.gz') as archive:
            names = archive.getnames()
        self.assertIn(f'data/subsample/{DATASET}/manifest.json', names)
        self.assertIn('workflow/run_hg008_20pct.sh', names)
        self.assertFalse(any(name.endswith('.fastq.gz') for name in names))
        self.assertIn('Código de saída do Nextflow: 0', result.stdout)

    def test_nextflow_failure_exit_is_preserved(self):
        result = self.run_script(MOCK_NF_EXIT='11')
        self.assertEqual(result.returncode, 11, result.stderr)
        self.assertIn('Código de saída do Nextflow: 11', result.stdout)

    def test_existing_results_not_overwritten(self):
        results = self.root / 'results' / DATASET
        results.mkdir(parents=True)
        sentinel = results / 'KEEP.txt'
        sentinel.write_text('USER-OWNED FIXTURE\n')
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Já existe', result.stderr)
        self.assertEqual(sentinel.read_text(), 'USER-OWNED FIXTURE\n')
        self.assertFalse((self.root / 'captured-command.json').exists())

    def test_broken_work_symlink_is_not_followed_or_overwritten(self):
        work = self.root / 'work'
        work.mkdir()
        link = work / DATASET
        link.symlink_to(self.root / 'missing-target')
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(link.is_symlink())

    def test_concurrent_launcher_lock_rejects_second_run(self):
        report_root = self.root / 'reports' / DATASET
        report_root.mkdir(parents=True)
        with (report_root / 'launcher.lock').open('w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('já está em execução', result.stderr)
        self.assertFalse((self.root / 'captured-command.json').exists())

    def test_no_screen_requires_opening_one_before_processing(self):
        result = self.run_script(STY='')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Abra uma screen', result.stderr)
        self.assertFalse((self.root / 'results').exists())

    def test_missing_conda_and_invalid_argument_stop_safely(self):
        result = self.run_script('--check', BRISANCE_CONDA_SH=str(self.root / 'missing.sh'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Conda não encontrado', result.stderr)
        result = self.run_script('--resume')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Uso:', result.stderr)
        self.assertFalse((self.root / 'results').exists())


if __name__ == '__main__':
    unittest.main()
