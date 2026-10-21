"""Synthetic tests for configuration only; no Nextflow, Docker, GPUs or real data."""

import contextlib
import copy
import csv
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'interface/configure_brisance.py'
spec = importlib.util.spec_from_file_location('brisance_configure', SCRIPT)
cfg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfg)


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='brisance-config-test-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.output = self.base / 'analysis_01'
        # Deliberately not valid FASTQ/BWA/VCF payloads: the assistant only
        # checks file metadata and must not imply scientific integrity checks.
        def placeholder(name):
            path = self.base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'placeholder-not-scientific-data\n')
            return str(path)
        self.rows = []
        for role in ('tumor', 'normal'):
            self.rows.append({'sample': role.upper(), 'role': role, 'pair_id': role + '_lane1',
                              'fastq_1': placeholder(role + '_R1.fastq.gz'),
                              'fastq_2': placeholder(role + '_R2.fastq.gz')})
        self.fasta = placeholder('reference.fa')
        for suffix in ('.fai', '.amb', '.ann', '.bwt', '.pac', '.sa'):
            placeholder('reference.fa' + suffix)
        placeholder('reference.dict')
        self.sites = [placeholder('sites_1.vcf.gz'), placeholder('sites_2.vcf.gz')]
        for site in self.sites:
            Path(site + '.tbi').write_bytes(b'placeholder\n')
        self.cache = self.base / 'vep_cache'
        info = self.cache / 'homo_sapiens/113_GRCh38/info.txt'
        info.parent.mkdir(parents=True)
        info.write_text('species homo_sapiens\nassembly GRCh38\nsource_assembly GRCh38.p14\n')
        resources = copy.deepcopy(cfg.DEFAULT_RESOURCES)
        resources['alignment']['gpu_devices'] = [7, 6, 5]
        resources['bqsr']['gpu_devices'] = [7]
        resources['calling']['gpu_devices'] = [7, 6]
        self.config = {'schema_version': 1, 'analysis_dir': str(self.output), 'samples': self.rows,
                       'reference': {'fasta': self.fasta, 'assembly': 'GRCh38',
                                     'known_sites': self.sites, 'vep_cache_dir': str(self.cache),
                                     'vep_cache_version': 113},
                       'trimming': {'adapter_mode': 'auto', 'adapter_r1': None, 'adapter_r2': None,
                                    'quality': 20, 'min_read_length': 20},
                       'resources': resources}

    def answers(self, save='yes'):
        answers = [str(self.output)]
        for row in self.rows:
            answers += [row['sample'], '', row['pair_id'], row['fastq_1'], row['fastq_2']]
        answers += [self.fasta, '', '2', *self.sites, str(self.cache), '', '', '', '7,6,5', '', '', '', save]
        return answers

    def run_assistant(self, answers):
        transcript = io.StringIO()
        iterator = iter(answers)
        def answer(prompt):
            transcript.write(prompt + '\n')
            return next(iterator)
        with mock.patch('builtins.input', side_effect=answer), mock.patch.object(sys.stdin, 'isatty', return_value=True), \
                contextlib.redirect_stdout(transcript), contextlib.redirect_stderr(transcript):
            code = cfg.main([])
        return code, transcript.getvalue()

    def test_valid_configuration_and_nonfixed_known_sites(self):
        validated = cfg.validate_configuration(self.config)
        self.assertEqual(len(validated['reference']['known_sites']), 2)
        self.assertEqual(validated['resources']['alignment']['gpu_devices'], [7, 6, 5])
        self.assertFalse(self.output.exists())

    def test_single_alignment_gpu_is_configurable_and_caller_can_use_other_gpu(self):
        self.config['resources']['alignment']['gpu_devices'] = [3]
        self.config['resources']['calling']['gpu_devices'] = [5]
        validated = cfg.validate_configuration(self.config)
        self.assertEqual(validated['resources']['alignment']['gpu_devices'], [3])

    def test_fastq_suffix_difference_cannot_collide_after_trimming(self):
        extra = copy.deepcopy(self.rows[0])
        extra['pair_id'] = 'tumor_lane2'
        for key in ('fastq_1', 'fastq_2'):
            path = Path(extra[key].replace('.fastq.gz', '.fq.gz'))
            path.write_bytes(b'different test placeholder')
            extra[key] = str(path)
        self.config['samples'].append(extra)
        with self.assertRaisesRegex(ValueError, 'collide after trimming'):
            cfg.validate_configuration(self.config)

    def test_custom_adapter_quality_and_length(self):
        self.config['trimming'] = {'adapter_mode': 'custom', 'adapter_r1': 'acgtn',
                                   'adapter_r2': 'TAGCA', 'quality': 25, 'min_read_length': 35}
        result = cfg.validate_configuration(self.config)
        self.assertEqual(result['trimming']['adapter_r1'], 'ACGTN')
        self.assertEqual(result['trimming']['min_read_length'], 35)

    def test_missing_or_invalid_custom_adapter_is_rejected(self):
        for value in (None, '', 'ACGT;touch', 'AC GT', 'ACGU'):
            with self.subTest(value=value):
                self.config['trimming']['adapter_mode'] = 'custom'
                self.config['trimming']['adapter_r1'] = value
                self.config['trimming']['adapter_r2'] = 'ACGT'
                with self.assertRaises(ValueError):
                    cfg.validate_configuration(self.config)

    def test_duplicate_fastq_and_hardlink_rejected(self):
        self.config['samples'][1]['fastq_1'] = self.rows[0]['fastq_1']
        with self.assertRaisesRegex(ValueError, 'used more than once'):
            cfg.validate_configuration(self.config)
        link = self.base / 'hardlink.fastq.gz'
        os.link(self.rows[0]['fastq_1'], link)
        self.config['samples'][1]['fastq_1'] = str(link)
        with self.assertRaisesRegex(ValueError, 'used more than once'):
            cfg.validate_configuration(self.config)

    def test_duplicate_samples_and_pair_ids_rejected(self):
        for field in ('sample', 'pair_id'):
            config = copy.deepcopy(self.config)
            config['samples'][1][field] = config['samples'][0][field]
            with self.assertRaises(ValueError):
                cfg.validate_configuration(config)

    def test_same_basenames_within_sample_rejected(self):
        extra = self.base / 'extra'
        extra.mkdir()
        copy1, copy2 = extra / 'tumor_R1.fastq.gz', extra / 'tumor_R2.fastq.gz'
        copy1.write_bytes(b'extra lane R1\n')
        copy2.write_bytes(b'extra lane R2\n')
        self.config['samples'].append({'sample': 'TUMOR', 'role': 'tumor', 'pair_id': 'tumor_lane2',
                                       'fastq_1': str(copy1), 'fastq_2': str(copy2)})
        with self.assertRaisesRegex(ValueError, 'distinct file names'):
            cfg.validate_configuration(self.config)

    def test_multiple_lanes_are_retained(self):
        extra1, extra2 = self.base / 'lane2_R1.fq.gz', self.base / 'lane2_R2.fq.gz'
        extra1.write_bytes(b'R1\n')
        extra2.write_bytes(b'R2\n')
        self.config['samples'].append({'sample': 'TUMOR', 'role': 'tumor', 'pair_id': 'tumor_lane2',
                                       'fastq_1': str(extra1), 'fastq_2': str(extra2)})
        self.assertEqual(len(cfg.validate_configuration(self.config)['samples']), 3)

    def test_missing_reference_index_and_site_index_rejected(self):
        path = Path(self.fasta + '.bwt')
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'reference.fa.bwt'):
            cfg.validate_configuration(self.config)
        path.write_bytes(b'index\n')
        Path(self.sites[1] + '.tbi').unlink()
        with self.assertRaisesRegex(ValueError, 'sites_2.vcf.gz.tbi'):
            cfg.validate_configuration(self.config)

    def test_alternate_dictionary_name(self):
        (self.base / 'reference.dict').rename(self.base / 'reference.fa.dict')
        self.assertEqual(cfg.validate_configuration(self.config)['reference']['fasta'], self.fasta)

    def test_duplicate_known_sites_rejected(self):
        self.config['reference']['known_sites'] = [self.sites[0], self.sites[0]]
        with self.assertRaisesRegex(ValueError, 'Duplicate known-sites'):
            cfg.validate_configuration(self.config)

    def test_cache_assembly_mismatch_rejected(self):
        info = self.cache / 'homo_sapiens/113_GRCh38/info.txt'
        info.write_text('species homo_sapiens\nassembly GRCh37\n')
        with self.assertRaisesRegex(ValueError, 'metadata'):
            cfg.validate_configuration(self.config)

    def test_grch37_can_be_recorded_but_is_labelled_unevaluated(self):
        path = self.cache / 'homo_sapiens/113_GRCh37/info.txt'
        path.parent.mkdir(parents=True)
        path.write_text('species homo_sapiens\nassembly GRCh37\n')
        self.config['reference']['assembly'] = 'GRCh37'
        validated = cfg.validate_configuration(self.config)
        summary = cfg.execution_summary(validated, cfg.storage_estimate(validated))
        self.assertIn('GRCh37/hg19 execution has not been evaluated', summary)

    def test_invalid_resources_and_unknown_fields_rejected(self):
        cases = [
            ('alignment', 'cpus', 0), ('alignment', 'cpus', True),
            ('alignment', 'gpu_devices', [7, 7]), ('bqsr', 'gpu_devices', [7, 6]),
            ('alignment', 'sorting_memory_gb', 256), ('trim', 'fastqc_heap_gb', 100),
            ('read_groups', 'index_threads', 10), ('calling', 'threads', '24; echo unsafe'),
            ('annotation', 'forks', -1),
        ]
        for stage, key, value in cases:
            with self.subTest(stage=stage, key=key, value=value):
                config = copy.deepcopy(self.config)
                config['resources'][stage][key] = value
                with self.assertRaises(ValueError):
                    cfg.validate_configuration(config)
        self.config['unexpected'] = 1
        with self.assertRaises(ValueError):
            cfg.validate_configuration(self.config)

    def test_paths_with_shell_characters_or_relative_paths_rejected(self):
        for value in ('relative/path', '/tmp/path with spaces', '/tmp/quote\'path', '/tmp/a;echo', '/tmp/a\nfile'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cfg.absolute_path(value)

    def test_estimate_uses_only_input_sizes_not_allocated_bytes_or_links(self):
        validated = cfg.validate_configuration(self.config)
        with mock.patch.object(Path, 'open', side_effect=AssertionError('must not read FASTQs')):
            estimate = cfg.storage_estimate(validated)
        size = sum(Path(row[key]).stat().st_size for row in self.rows for key in ('fastq_1', 'fastq_2'))
        self.assertEqual(estimate['input_bytes'], size)
        self.assertEqual(estimate['estimated_additional_bytes'], size * 5)
        self.assertEqual(estimate['recommended_available_bytes'], max(size * 8, 32 * cfg.GIB))

    def test_low_storage_warning_allows_saving_config_only(self):
        validated = cfg.validate_configuration(self.config)
        with mock.patch.object(cfg.shutil, 'disk_usage', return_value=mock.Mock(free=0)):
            estimate = cfg.storage_estimate(validated)
        summary = cfg.execution_summary(validated, estimate)
        self.assertIn('below the recommendation', summary)
        self.assertIn('not approval to start processing', summary)

    def test_successful_save_creates_one_folder_and_only_regular_small_files(self):
        validated = cfg.validate_configuration(self.config)
        estimate = cfg.storage_estimate(validated)
        cfg.save_configuration(validated, estimate, cfg.execution_summary(validated, estimate))
        self.assertEqual(set(item.name for item in self.output.iterdir()),
                         {'brisance.json', 'samplesheet.csv', 'results', 'reports', 'work'})
        for path in self.output.rglob('*'):
            self.assertFalse(path.is_symlink())
            if path.is_file():
                self.assertLess(path.stat().st_size, 20000)
        with (self.output / 'samplesheet.csv').open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows, validated['samples'])
        self.assertEqual(cfg.validate_configuration(json.loads((self.output / 'brisance.json').read_text())), validated)

    def test_existing_destination_not_overwritten(self):
        self.output.mkdir()
        marker = self.output / 'keep.txt'
        marker.write_text('keep\n')
        with self.assertRaises(ValueError):
            cfg.save_configuration(self.config, {}, '')
        self.assertEqual(marker.read_text(), 'keep\n')
        self.assertEqual(len(list(self.output.iterdir())), 1)

    def test_cancel_default_writes_nothing_and_never_runs_subprocesses(self):
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('No external commands allowed')):
            code, transcript = self.run_assistant(self.answers(save=''))
        self.assertEqual(code, 0, transcript)
        self.assertIn('Cancelled', transcript)
        self.assertFalse(self.output.exists())

    def test_interactive_save_and_read_only_check(self):
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('No external commands allowed')):
            code, transcript = self.run_assistant(self.answers())
        self.assertEqual(code, 0, transcript)
        self.assertIn('No analysis started', transcript)
        before = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in self.output.rglob('*') if p.is_file()}
        checked = io.StringIO()
        with contextlib.redirect_stdout(checked):
            result = cfg.main(['--check', str(self.output / 'brisance.json')])
        self.assertEqual(result, 0, checked.getvalue())
        self.assertIn('CONFIGURATION CHECK OK', checked.getvalue())
        self.assertEqual(before, {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in self.output.rglob('*') if p.is_file()})

    def test_noninteractive_invocation_fails_without_creating_folders(self):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT)], input='', capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('interactive terminal', result.stderr)
        self.assertFalse(self.output.exists())

    def test_interrupt_before_confirmation_creates_nothing(self):
        with mock.patch('builtins.input', side_effect=KeyboardInterrupt), \
                mock.patch.object(sys.stdin, 'isatty', return_value=True), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = cfg.main([])
        self.assertEqual(code, 130)
        self.assertFalse(self.output.exists())

    def test_configuration_does_not_modify_inputs_or_shared_resources(self):
        originals = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                     for p in self.base.rglob('*') if p.is_file()}
        code, transcript = self.run_assistant(self.answers())
        self.assertEqual(code, 0, transcript)
        self.assertEqual(originals, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in originals})

    def test_unknown_confirmation_is_not_accepted_as_yes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result = cfg.yes_no('Save?', input_fn=mock.Mock(side_effect=['maybe', '']))
        self.assertFalse(result)

    def test_missing_parent_or_existing_symlink_destination_rejected(self):
        with self.assertRaises(ValueError):
            cfg.new_destination(str(self.base / 'not-there/analysis'))
        link = self.base / 'analysis_link'
        link.symlink_to(self.base / 'missing-target')
        with self.assertRaises(ValueError):
            cfg.new_destination(str(link))

    def test_optional_preflight_only_runs_after_save_and_propagates_failure(self):
        answers = iter(self.answers())
        with mock.patch('builtins.input', side_effect=lambda text: next(answers)), \
                mock.patch.object(sys.stdin, 'isatty', return_value=True), \
                mock.patch.object(subprocess, 'run', return_value=mock.Mock(returncode=1)) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            code = cfg.main(['--preflight', '--java', '/selected/java', '--nextflow', '/selected/nextflow', '--no-download'])
        self.assertEqual(code, 1)
        command = run.call_args.args[0]
        self.assertIn(str(self.output / 'brisance.json'), command)
        self.assertIn('--no-download', command)
        self.assertIn('/selected/java', command)
        self.assertIn('/selected/nextflow', command)
        self.assertTrue((self.output / 'brisance.json').exists())

    def test_cancel_in_preflight_mode_never_runs_environment_checks(self):
        answers = iter(self.answers(save='no'))
        with mock.patch('builtins.input', side_effect=lambda text: next(answers)), \
                mock.patch.object(sys.stdin, 'isatty', return_value=True), \
                mock.patch.object(subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
            code = cfg.main(['--preflight'])
        self.assertEqual(code, 0)
        run.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_human_units_disambiguate_decimal_and_binary(self):
        self.assertEqual(cfg.human_bytes(1024 ** 4), '1.00 TiB (1.10 TB)')

    def test_empty_files_and_single_end_inputs_rejected(self):
        Path(self.rows[0]['fastq_1']).write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'empty file'):
            cfg.validate_configuration(self.config)
        del self.config['samples'][0]['fastq_2']
        with self.assertRaisesRegex(ValueError, 'Sample entries'):
            cfg.validate_configuration(self.config)


if __name__ == '__main__':
    unittest.main()
