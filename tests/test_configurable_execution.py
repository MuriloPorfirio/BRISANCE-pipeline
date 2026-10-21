"""Runner safety and optional real Nextflow orchestration, NOT biological validation."""
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'interface'))
import execute_analysis as execution
sys.path.pop(0)


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ConfigurationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.config = fixtures.cfg.validate_configuration(copy.deepcopy(self.fixture.config))
        self.images = {name: 'sha256:' + str(number) * 64 for number, name in enumerate(execution.IMAGE_KEYS, 1)}
        estimate = fixtures.cfg.storage_estimate(self.config)
        fixtures.cfg.save_configuration(self.config, estimate, fixtures.cfg.execution_summary(self.config, estimate))

    def test_lowering_preserves_every_user_setting_and_explicit_known_sites(self):
        self.config['trimming'].update(adapter_mode='custom', adapter_r1='ACGT', adapter_r2='TGCA', quality=25)
        params = execution.execution_parameters(self.config, self.images)
        self.assertEqual(params['configuration'], self.config)
        self.assertEqual(params['images'], self.images)
        self.assertEqual(len(params['bundle']['known_indices']), 2)
        self.assertEqual(len(params['bundle']['reference_indices']), 7)
        self.assertTrue(params['bundle']['cache_info'].endswith('113_GRCh38/info.txt'))

    def test_wrong_or_missing_image_ids_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'immutable'):
            execution.execution_parameters(self.config, dict(self.images, vep='ensemblorg/ensembl-vep:latest'))
        with self.assertRaisesRegex(ValueError, 'immutable'):
            execution.execution_parameters(self.config, {})

    def test_existing_output_or_work_is_never_overwritten(self):
        execution.fresh_outputs(self.config)
        for directory in ('work', 'results'):
            path = self.fixture.output / directory / 'keep-this-file'
            path.write_text('owned by user')
            with self.assertRaisesRegex(ValueError, 'empty real directory'):
                execution.fresh_outputs(self.config)
            self.assertEqual(path.read_text(), 'owned by user')
            path.unlink()

    def test_publication_is_regular_and_survives_work_name_removal(self):
        execution.publication_probe(self.config)
        self.assertEqual(list((self.fixture.output / 'work').iterdir()), [])
        self.assertEqual(list((self.fixture.output / 'results').iterdir()), [])

    def test_publication_failure_cleans_only_owned_tiny_probes(self):
        with mock.patch.object(execution.os, 'link', side_effect=OSError('hard links unsupported')):
            with self.assertRaises(OSError):
                execution.publication_probe(self.config)
        self.assertEqual(list((self.fixture.output / 'work').iterdir()), [])
        self.assertEqual(list((self.fixture.output / 'results').iterdir()), [])

    def test_publication_collision_does_not_delete_someone_elses_file(self):
        collisions = []
        def concurrent_file(source, target):
            Path(target).write_text('unrelated concurrent file')
            collisions.append(Path(target))
            raise FileExistsError('concurrent file')
        with mock.patch.object(execution.os, 'link', side_effect=concurrent_file):
            with self.assertRaises(FileExistsError):
                execution.publication_probe(self.config)
        self.assertEqual(collisions[0].read_text(), 'unrelated concurrent file')
        self.assertEqual(list((self.fixture.output / 'work').iterdir()), [])

    def test_run_cannot_skip_environment_checks(self):
        with self.assertRaisesRegex(ValueError, 'check_environment = true'):
            execution.execute(self.config, {'check_environment': False}, 'settings-record')

    def test_failed_environment_never_starts_nextflow(self):
        runtime = {'check_environment': True}
        with mock.patch.object(execution, 'check_environment', side_effect=RuntimeError('probe failed')), \
                mock.patch.object(execution, 'stream_command') as start:
            with self.assertRaisesRegex(RuntimeError, 'probe failed'):
                execution.execute(self.config, runtime, 'settings-record')
        start.assert_not_called()

    def prepared_checker(self):
        checker = mock.Mock()
        checker.images = {spec['image']: self.images[key] for key, spec in zip(execution.IMAGE_KEYS, execution.environment.IMAGES)}
        checker.report = {'checks': [{'name': 'Nextflow 26.04.6', 'details': {'executable': '/verified/nextflow'}}]}
        checker.directory = self.fixture.output / 'reports' / 'environment-test'
        checker.directory.mkdir()
        checker.env = dict(os.environ, JAVA_CMD='/verified/java')
        return checker

    def test_final_refusal_runs_only_metadata_validation(self):
        checker = self.prepared_checker()
        with mock.patch.object(execution, 'check_environment', return_value=checker), \
                mock.patch.object(execution.configuration, 'yes_no', return_value=False), \
                mock.patch.object(execution, 'stream_command', return_value=0) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            code = execution.execute(self.config, {'check_environment': True}, 'settings-record')
        self.assertEqual(code, 0)
        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertEqual(command[command.index('--mode') + 1], 'validate')
        self.assertEqual(list((self.fixture.output / 'work').iterdir()), [])
        self.assertFalse(list((self.fixture.output / 'reports').glob('execution-*/start.json')))

    def test_confirmed_launch_pins_checked_ids_and_snapshots_source_without_resume(self):
        checker = self.prepared_checker()
        with mock.patch.object(execution, 'check_environment', return_value=checker), \
                mock.patch.object(execution.configuration, 'yes_no', return_value=True), \
                mock.patch.object(execution, 'stream_command', return_value=0) as run, \
                mock.patch.object(execution, 'completion_check', return_value={'final_vcf': '/test/result', 'counts': {'PASS_TLOD': 0}}), \
                contextlib.redirect_stdout(io.StringIO()):
            code = execution.execute(self.config, {'check_environment': True}, 'settings-record')
        self.assertEqual(code, 0)
        self.assertEqual(run.call_count, 2)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index('--mode') + 1], 'run')
        self.assertIn('-C', command)
        self.assertNotIn('-resume', command)
        params = json.loads(Path(command[command.index('-params-file') + 1]).read_text())
        self.assertEqual(params['images'], self.images)
        directory = next((self.fixture.output / 'reports').glob('execution-*'))
        self.assertEqual((directory / 'source/pipeline/main.nf').read_bytes(), (ROOT / 'pipeline/main.nf').read_bytes())
        self.assertEqual(json.loads((directory / 'completion.json').read_text())['status'], 'completed')
        checker.step.assert_called_once()

    def test_validation_failure_never_reaches_final_prompt_or_analysis(self):
        checker = self.prepared_checker()
        with mock.patch.object(execution, 'check_environment', return_value=checker), \
                mock.patch.object(execution.configuration, 'yes_no') as ask, \
                mock.patch.object(execution, 'stream_command', return_value=17) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            code = execution.execute(self.config, {'check_environment': True}, 'settings-record')
        self.assertEqual(code, 17)
        ask.assert_not_called()
        run.assert_called_once()

    def test_launch_failure_is_recorded_with_original_exit_code(self):
        checker = self.prepared_checker()
        with mock.patch.object(execution, 'check_environment', return_value=checker), \
                mock.patch.object(execution.configuration, 'yes_no', return_value=True), \
                mock.patch.object(execution, 'stream_command', side_effect=[0, 19]), \
                mock.patch.object(execution, 'completion_check') as complete, \
                contextlib.redirect_stdout(io.StringIO()):
            code = execution.execute(self.config, {'check_environment': True}, 'settings-record')
        self.assertEqual(code, 19)
        complete.assert_not_called()
        directory = next((self.fixture.output / 'reports').glob('execution-*'))
        record = json.loads((directory / 'completion.json').read_text())
        self.assertEqual((record['status'], record['exit_code']), ('failed', 19))

    def test_failed_or_incomplete_trace_is_not_success(self):
        directory = self.fixture.base / 'run-report'
        directory.mkdir()
        (directory / 'trace.tsv').write_text('status\texit\nCOMPLETED\t0\n')
        with self.assertRaisesRegex(ValueError, 'all expected'):
            execution.completion_check(self.config, directory)

    def test_regular_stream_logs_and_preserves_exit_code(self):
        directory = self.fixture.base / 'stream'
        directory.mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            code = execution.stream_command([sys.executable, '-c', 'print("test log"); raise SystemExit(7)'], directory, dict(os.environ))
        self.assertEqual(code, 7)
        self.assertIn('test log', (directory / 'console.log').read_text())

    @unittest.skipUnless(os.environ.get('BRISANCE_NEXTFLOW_TEST'), 'Set BRISANCE_NEXTFLOW_TEST for real Nextflow with fake scientific tools and a fake Docker CLI (no daemon).')
    def test_real_nextflow_full_graph_with_fake_tools(self):
        self.run_real_graph(custom=True)

    @unittest.skipUnless(os.environ.get('BRISANCE_NEXTFLOW_TEST'), 'Set BRISANCE_NEXTFLOW_TEST for real Nextflow with fake scientific tools and a fake Docker CLI (no daemon).')
    def test_real_nextflow_automatic_adapters_and_multiple_tumor_lanes(self):
        self.run_real_graph(custom=False)

    def run_real_graph(self, custom):
        # Deliberately change many settings: propagation, not HG008 defaults.
        c = self.config
        if custom:
            c['trimming'].update(adapter_mode='custom', adapter_r1='ACGTN', adapter_r2='TAGCA', quality=25, min_read_length=35)
        else:
            lane = copy.deepcopy(c['samples'][0])
            lane['pair_id'] = 'tumor_lane2'
            for key in ('fastq_1', 'fastq_2'):
                path = self.fixture.base / ('lane2_' + Path(lane[key]).name)
                path.write_text('TEST INPUT PLACEHOLDER ONLY')
                lane[key] = str(path)
            c['samples'].append(lane)
        c['resources']['alignment'].update(bwa_thread_pool=11, sorting_memory_gb=64, gpu_devices=[4])
        c['resources']['bqsr'].update(threads=7, gpu_devices=[3])
        c['resources']['calling'].update(threads=9, gpu_devices=[2])
        c['resources']['read_groups']['index_threads'] = 3
        c['resources']['filtering']['java_heap_gb'] = 3
        c['resources']['annotation']['forks'] = 2
        # A fake Docker CLI records the wrapper and runs fake tools on this host.
        # No daemon/containers/GPUs are used. Keep local scheduling limits small.
        for stage in c['resources'].values():
            stage.update(cpus=1, memory_gb=1)
        params = execution.execution_parameters(c, self.images)
        parameter_file = self.fixture.base / 'params.json'
        execution.write_json(parameter_file, params)
        test_config = self.fixture.base / 'test.config'
        test_config.write_text((ROOT / 'pipeline/nextflow.config').read_text() +
                               "\ntrace.fields = 'task_id,name,status,exit,container,cpus,memory'\n")
        binary_dir = self.fixture.base / 'fake-bin'
        binary_dir.mkdir()
        for name in ('docker', 'trim_galore', 'cutadapt', 'fastqc', 'pbrun', 'samtools', 'bcftools', 'gatk', 'vep'):
            path = binary_dir / name
            shutil.copyfile(ROOT / 'tests/fake_scientific_tool.py', path)
            path.chmod(0o700)
        env = dict(os.environ, NXF_OFFLINE='true', NXF_DISABLE_CHECK_LATEST='true',
                   NXF_HOME=str(self.fixture.base / 'nxf-home'),
                   PATH=str(binary_dir) + os.pathsep + os.environ['PATH'],
                   BRISANCE_TEST_TOOL_LOG=str(self.fixture.base / 'tool-calls.jsonl'))
        common = [os.environ['BRISANCE_NEXTFLOW_TEST'], '-C', str(test_config), 'run',
                  str(ROOT / 'pipeline/main.nf'), '-params-file', str(parameter_file),
                  '-work-dir', str(self.fixture.output / 'work'), '-ansi-log', 'false']
        validation = subprocess.run(common + ['--mode', 'validate'], cwd=self.fixture.base, env=env,
                                    capture_output=True, text=True, timeout=120)
        self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
        self.assertIn('all stages loaded', validation.stdout)
        self.assertFalse((self.fixture.base / 'tool-calls.jsonl').exists())
        run = self.fixture.base / 'nf-run'
        run.mkdir()
        result = subprocess.run(common + ['--mode', 'run', '-with-trace', str(run / 'trace.tsv')],
            cwd=self.fixture.base, env=env, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with (run / 'trace.tsv').open(newline='') as handle:
            trace = list(csv.DictReader(handle, delimiter='\t'))
        expected_images = {'TRIM_GALORE': 'trim', 'FQ2BAM': 'parabricks', 'APPLY_BQSR': 'parabricks',
            'ADJUST_READ_GROUPS': 'samtools', 'MUTECT_CALLER': 'parabricks', 'COMPRESS_RAW_VCF': 'bcftools',
            'FILTER_MUTECT_CALLS': 'gatk', 'SELECT_PASS': 'bcftools', 'ANNOTATE_VEP': 'vep',
            'INDEX_VEP': 'bcftools', 'SELECT_POSITIVE_TLOD': 'bcftools'}
        for task in trace:
            name = task['name'].split(' (', 1)[0]
            self.assertEqual(task['container'], self.images[expected_images[name]], task['name'])
        self.assertNotIn('Access to undefined parameter', validation.stdout + validation.stderr)
        self.assertNotIn('Access to undefined parameter', result.stdout + result.stderr)
        completion = execution.completion_check(c, run)
        self.assertEqual(completion['tasks_completed'], len(c['samples']) + 13)
        self.assertEqual(completion['counts']['PASS_TLOD'], 0)
        calls = [json.loads(line) for line in (self.fixture.base / 'tool-calls.jsonl').read_text().splitlines()]
        def invocation(tool, option=None):
            return next(row['args'] for row in calls if row['tool'] == tool and
                        '--version' not in row['args'] and '--help' not in row['args'] and
                        (option is None or option in row['args']))
        trim = invocation('trim_galore')
        trim_options = [('--quality', str(c['trimming']['quality'])), ('--length', str(c['trimming']['min_read_length']))]
        if custom:
            trim_options += [('--adapter', 'ACGTN'), ('--adapter2', 'TAGCA')]
        else:
            self.assertNotIn('--adapter', trim)
            self.assertNotIn('--adapter2', trim)
        for flag, value in trim_options:
            self.assertEqual(trim[trim.index(flag) + 1], value)
        align = next(row['args'] for row in calls if row['tool'] == 'pbrun' and 'TUMOR.bam' in row['args'])
        self.assertEqual(align[align.index('--num-gpus') + 1], '1')
        self.assertEqual(align[align.index('--bwa-cpu-thread-pool') + 1], '11')
        self.assertEqual(align.count('--knownSites'), 2)
        self.assertEqual(align.count('--in-fq'), 1 if custom else 2)
        self.assertEqual(invocation('pbrun', 'applybqsr')[invocation('pbrun', 'applybqsr').index('--num-threads') + 1], '7')
        self.assertIn('9', invocation('pbrun', 'mutectcaller'))
        self.assertIn('3', invocation('samtools', 'index'))
        self.assertIn('-Xmx3g', invocation('gatk')[1])
        self.assertEqual(invocation('vep')[invocation('vep').index('--fork') + 1], '2')
        # Hard links, not symbolic shortcuts: deleting a work name does not break results.
        vcf = Path(completion['final_vcf'])
        work_copy = next(path for path in (self.fixture.output / 'work').rglob(vcf.name) if not path.is_symlink())
        self.assertTrue(os.path.samefile(vcf, work_copy))
        work_copy.unlink()
        self.assertTrue(vcf.is_file())
        self.assertFalse(vcf.is_symlink())


if __name__ == '__main__':
    unittest.main()
