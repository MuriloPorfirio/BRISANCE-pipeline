"""Shell wrapper tests with fake Conda/Java/NF/helper; never a WGS execution."""
import fcntl
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'run_hg008_100pct.sh'


class FullLauncherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='brisance-full-wrapper-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        workflow = self.root / 'workflow'
        workflow.mkdir()
        self.script = workflow / SOURCE.name
        shutil.copy2(SOURCE, self.script)
        self.fake_env = self.root / 'fake-conda'
        (self.fake_env / 'lib/jvm/bin').mkdir(parents=True)
        (self.fake_env / 'bin').mkdir()
        java = self.fake_env / 'lib/jvm/bin/java'
        java.write_text('#!/bin/sh\necho \'openjdk version "21-MOCK"\' >&2\n')
        java.chmod(0o755)
        (self.fake_env / 'bin/java').symlink_to(java)
        self.conda = self.root / 'conda.sh'
        self.conda.write_text('conda() { export CONDA_PREFIX=' + shlex.quote(str(self.fake_env)) + '; }\n')
        self.fakebin = self.root / 'fakebin'
        self.fakebin.mkdir()
        for name in ('docker', 'nvidia-smi'):
            path = self.fakebin / name
            path.write_text('#!/bin/sh\nexit 0\n')
            path.chmod(0o755)
        nf = self.root / 'nextflow-26.04.6-dist'
        nf.write_text('#!/bin/sh\necho "Nextflow version 26.04.6 MOCK"\n')
        nf.chmod(0o755)
        (workflow / 'hg008_full_run.py').write_text('''import os, sys
from pathlib import Path
home = Path(os.environ['CONDA_PREFIX']) / 'lib/jvm'
assert os.environ['JAVA_CMD'] == str(home / 'bin/java')
assert os.environ['NXF_JAVA_HOME'] == str(home)
if '--check-paths' in sys.argv:
    pass
elif '--check' in sys.argv:
    print('MOCK check only; no processing')
elif '--run' in sys.argv:
    folder = Path(sys.argv[sys.argv.index('--reports') + 1])
    assert folder.parent.name == 'hg008-100pct'
    (folder / 'MOCK-only.txt').write_text('Not a pipeline result')
    print('MOCK child helper, NOT an actual workflow')
    sys.exit(int(os.environ.get('MOCK_FULL_EXIT', '0')))
else:
    raise SystemExit(2)
''')
        self.env = dict(os.environ, BRISANCE_CONDA_SH=str(self.conda), STY='MOCK-screen',
                        JAVA_CMD='/usr/bin/java', JAVA_HOME='', NXF_JAVA_HOME='/wrong',
                        PATH=str(self.fakebin) + os.pathsep + os.environ['PATH'])

    def run_script(self, *arguments, **environment):
        return subprocess.run(['bash', str(self.script), *arguments], cwd='/tmp',
                              env=dict(self.env, **environment), text=True,
                              capture_output=True, timeout=20)

    def test_no_argument_never_starts(self):
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'reports').exists())

    def test_check_works_without_screen_and_overrides_old_java(self):
        result = self.run_script('--check', STY='')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.fake_env / 'lib/jvm/bin/java'), result.stdout)
        self.assertIn('MOCK check only', result.stdout)
        self.assertFalse((self.root / 'reports').exists())

    def test_run_requires_screen(self):
        result = self.run_script('--run', STY='')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Abra uma screen', result.stderr)
        self.assertFalse((self.root / 'reports').exists())

    def test_explicit_run_gets_its_own_report(self):
        result = self.run_script('--run')
        self.assertEqual(result.returncode, 0, result.stderr)
        reports = list((self.root / 'reports/hg008-100pct').glob('execution-*'))
        self.assertEqual(len(reports), 1)
        self.assertTrue((reports[0] / 'console.log').is_file())
        self.assertTrue((reports[0] / 'MOCK-only.txt').is_file())
        self.assertIn('Código de saída do launcher: 0', result.stdout)

    def test_helper_failure_is_propagated(self):
        result = self.run_script('--run', MOCK_FULL_EXIT='88')
        self.assertEqual(result.returncode, 88)
        self.assertIn('Código de saída do launcher: 88', result.stdout)

    def test_concurrent_launcher_blocked(self):
        folder = self.root / 'reports/hg008-100pct'
        folder.mkdir(parents=True)
        with (folder / 'launcher.lock').open('w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_script('--run')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('já está em execução', result.stderr)
        self.assertFalse(list(folder.glob('execution-*')))

    def test_invalid_flag_refused(self):
        self.assertNotEqual(self.run_script('--resume').returncode, 0)


if __name__ == '__main__':
    unittest.main()
