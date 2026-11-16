"""Optional BAM/PoN/QC settings and real-Nextflow orchestration with test doubles."""
import contextlib
import copy
import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest import mock

import test_configuration_assistant as fixtures
import test_fixed_settings as fixed_tests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'interface'))
import execute_analysis as execution
import configure_brisance as cfg
import run_from_file as fixed


class BamPonQcTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ConfigurationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.config = copy.deepcopy(self.fixture.config)
        self.config['input_mode'] = 'bam'
        self.config['reference']['known_sites'] = []
        Path(self.fixture.fasta + '.fai').write_text('chr1\t100\t6\t100\t101\n')
        self.config['samples'] = []
        for role in ('tumor', 'normal'):
            bam = self.fixture.base / (role.upper() + '.bam')
            bam.write_text('TEST DOUBLE BAM ONLY\n')
            Path(str(bam) + '.bai').write_text('TEST DOUBLE BAI ONLY\n')
            self.config['samples'].append({'sample': role.upper(), 'role': role, 'bam': str(bam), 'bam_index': str(bam) + '.bai'})
        self.pon = self.fixture.base / 'input_pon.vcf.gz'
        for suffix in ('', '.tbi', '.pon'):
            Path(str(self.pon) + suffix).write_text('TEST DOUBLE PoN ONLY\n')
        self.images = {name: 'sha256:' + str(i) * 64 for i, name in enumerate(execution.IMAGE_KEYS, 1)}

    def test_bam_does_not_require_fastqs_knownsites_or_bwa_indices(self):
        for row in self.fixture.rows:
            Path(row['fastq_1']).unlink()
            Path(row['fastq_2']).unlink()
        for suffix in ('.amb', '.ann', '.bwt', '.pac', '.sa'):
            Path(self.fixture.fasta + suffix).unlink()
        normalized = cfg.validate_configuration(self.config)
        self.assertEqual(len(execution.execution_parameters(normalized, self.images)['bundle']['reference_indices']), 2)
        estimate = cfg.storage_estimate(normalized)
        self.assertEqual(estimate['recommended_available_bytes'], 64 * 1024 ** 3)
        self.assertIn('no trimming', cfg.execution_summary(normalized, estimate))

    def test_bam_names_roles_and_reused_files_are_rejected(self):
        for change in ('sample', 'role', 'bam'):
            bad = copy.deepcopy(self.config)
            bad['samples'][1][change] = bad['samples'][0][change]
            with self.assertRaises(ValueError):
                cfg.validate_configuration(bad)

    def test_prepared_pon_requires_index_and_boolean_and_normalizes(self):
        self.config['somatic'] = {'pon': str(self.pon), 'pon_prepared': True}
        self.config['qc'] = {'enabled': True}
        self.assertEqual(cfg.validate_configuration(self.config), self.config)
        self.config['somatic']['pon_prepared'] = 'true'
        with self.assertRaises(ValueError):
            cfg.validate_configuration(self.config)
        self.config['somatic']['pon_prepared'] = True
        Path(str(self.pon) + '.pon').unlink()
        with self.assertRaises(ValueError):
            cfg.validate_configuration(self.config)

    def test_ini_bam_and_optional_flags_round_trip(self):
        lines = ['[analysis]', 'folder = ' + self.config['analysis_dir'], 'input_mode = bam']
        for row in self.config['samples']:
            lines += ['[' + row['role'] + ']', 'sample = ' + row['sample'], 'bam = ' + row['bam']]
        lines += ['[reference]', 'fasta = ' + self.fixture.fasta, 'vep_cache = ' + str(self.fixture.cache),
                  '[calling]', 'gpus = 6', '[somatic]', 'pon = ' + str(self.pon), 'pon_prepared = true', '[qc]', 'enabled = true']
        content = '\n'.join(lines)
        parsed, _ = fixed.parse_settings('/synthetic/settings.ini', content=content)
        checked = cfg.validate_configuration(parsed)
        self.assertEqual(checked['somatic'], {'pon': str(self.pon), 'pon_prepared': True})
        self.assertEqual(checked['samples'], self.config['samples'])
        self.assertTrue(checked['qc']['enabled'])
        with self.assertRaisesRegex(ValueError, 'mix BAM and FASTQ'):
            fixed.parse_settings('/synthetic/settings.ini', content=content.replace('sample = TUMOR', 'sample = TUMOR\nr1 = /test.fastq.gz'))

    def test_legacy_defaults_are_identical_when_disabled(self):
        old = copy.deepcopy(self.fixture.config)
        for row in old['samples']:
            row['pair_id'] = row['sample'] + '_pair1'
        content = fixed_tests.render(old) + '\n[somatic]\npon =\npon_prepared = false\n[qc]\nenabled = false\n'
        parsed, _ = fixed.parse_settings('/synthetic/settings.ini', content=content)
        self.assertEqual(cfg.validate_configuration(parsed), old)

    def test_saved_bam_samplesheet_is_consistent(self):
        c = cfg.validate_configuration(self.config)
        estimate = cfg.storage_estimate(c)
        cfg.save_configuration(c, estimate, cfg.execution_summary(c, estimate))
        self.assertTrue(fixed.existing_configuration(c))
        with (Path(c['analysis_dir']) / 'samplesheet.csv').open() as h:
            self.assertEqual(list(csv.DictReader(h)), c['samples'])

    def test_expected_task_counts(self):
        self.assertEqual(execution.expected_tasks(self.config), 9)
        self.config['qc'] = {'enabled': True}
        self.config['somatic'] = {'pon': str(self.pon), 'pon_prepared': True}
        self.assertEqual(execution.expected_tasks(self.config), 13)
        self.config['somatic']['pon_prepared'] = False
        self.assertEqual(execution.expected_tasks(self.config), 14)

    def test_unattended_run_records_authorization_and_disables_downloads(self):
        c = copy.deepcopy(self.fixture.config)
        ini = self.fixture.base / 'authorized.ini'
        ini.write_text(fixed_tests.render(c))
        with mock.patch.object(sys.stdin, 'isatty', return_value=False), \
                mock.patch.object(execution, 'execute', return_value=0) as run, \
                mock.patch.object(fixed.configuration, 'yes_no') as ask, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fixed.main([str(ini), '--run', '--yes']), 0)
        ask.assert_not_called()
        self.assertFalse(run.call_args.args[1]['allow_downloads'])
        self.assertTrue(run.call_args.kwargs['approved'])
        self.assertEqual(len(list(self.fixture.output.glob('reports/settings-*/unattended-authorization.txt'))), 1)

    @unittest.skipUnless(os.environ.get('BRISANCE_NEXTFLOW_TEST'), 'Optional real Nextflow / fake tools test.')
    def test_bam_graph_without_optional_features(self):
        self.graph()

    @unittest.skipUnless(os.environ.get('BRISANCE_NEXTFLOW_TEST'), 'Optional real Nextflow / fake tools test.')
    def test_bam_graph_with_prepared_pon_and_qc(self):
        self.graph(pon=True, prepared=True, qc=True)

    @unittest.skipUnless(os.environ.get('BRISANCE_NEXTFLOW_TEST'), 'Optional real Nextflow / fake tools test.')
    def test_bam_graph_with_automatic_pon_and_qc(self):
        self.graph(pon=True, prepared=False, qc=True)

    @unittest.skipUnless(os.environ.get('BRISANCE_NEXTFLOW_TEST'), 'Optional real Nextflow / fake tools test.')
    def test_fastq_graph_with_pon_and_qc(self):
        self.config = copy.deepcopy(self.fixture.config)
        self.graph(pon=True, prepared=False, qc=True)

    def graph(self, pon=False, prepared=False, qc=False):
        c = self.config
        if pon:
            c['somatic'] = {'pon': str(self.pon), 'pon_prepared': prepared}
        if qc:
            c['qc'] = {'enabled': True}
        c = cfg.validate_configuration(c)
        estimate = cfg.storage_estimate(c)
        cfg.save_configuration(c, estimate, cfg.execution_summary(c, estimate))
        for res in c['resources'].values():
            res.update(cpus=1, memory_gb=1)
        params = self.fixture.base / 'params.json'
        execution.write_json(params, execution.execution_parameters(c, self.images))
        bin_dir = self.fixture.base / 'bin'
        bin_dir.mkdir()
        for tool in ('docker', 'trim_galore', 'cutadapt', 'fastqc', 'pbrun', 'samtools', 'bcftools', 'gatk', 'vep'):
            target = bin_dir / tool
            shutil.copyfile(ROOT / 'tests/fake_scientific_tool.py', target)
            target.chmod(0o700)
        env = dict(os.environ, NXF_OFFLINE='true', NXF_DISABLE_CHECK_LATEST='true', NXF_HOME=str(self.fixture.base / 'nxf'),
                   PATH=str(bin_dir) + os.pathsep + os.environ['PATH'], BRISANCE_TEST_TOOL_LOG=str(self.fixture.base / 'calls.jsonl'))
        run = self.fixture.base / 'run'
        run.mkdir()
        common = [os.environ['BRISANCE_NEXTFLOW_TEST'], '-C', str(ROOT / 'pipeline/nextflow.config'),
                  'run', str(ROOT / 'pipeline/main.nf'), '-params-file', str(params), '-work-dir', c['analysis_dir'] + '/work', '-ansi-log', 'false']
        result = subprocess.run(common + ['--mode', 'validate'], cwd=run, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.fixture.base / 'calls.jsonl').exists())
        result = subprocess.run(common + ['--mode', 'run', '-with-trace', str(run / 'trace.tsv')], cwd=run, env=env, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        completion = execution.completion_check(c, run)
        self.assertEqual(completion['tasks_completed'], execution.expected_tasks(c))
        calls = [json.loads(line) for line in (self.fixture.base / 'calls.jsonl').read_text().splitlines()]
        pbrun = [row['args'] for row in calls if row['tool'] == 'pbrun' and '--version' not in row['args']]
        caller = next(row for row in pbrun if row[0] == 'mutectcaller')
        self.assertEqual('--pon' in caller, pon)
        self.assertEqual(sum(row[0] == 'collectmultiplemetrics' for row in pbrun), 2 if qc else 0)
        self.assertEqual(sum(row[0] == 'prepon' for row in pbrun), int(pon and not prepared))
        self.assertEqual(sum(row[0] == 'postpon' for row in pbrun), int(pon))
        if cfg.bam_mode(c):
            self.assertFalse(any(row[0] in ('fq2bam', 'applybqsr') for row in pbrun))
            self.assertFalse(any(row['tool'] == 'trim_galore' for row in calls))
        self.assertFalse(any(path.is_symlink() for path in (Path(c['analysis_dir']) / 'results').rglob('*')))


if __name__ == '__main__':
    unittest.main()
