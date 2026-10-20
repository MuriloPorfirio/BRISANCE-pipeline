"""Synthetic tests of orchestration and safety, not biological results or seqtk RNG."""

import csv
import gzip
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('prepare_fraction_test', ROOT / 'prepare_fraction_test.py')
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


def sample_mock(source, destination, seed, fraction, log):
    """Python RNG mock deliberately does not claim to reproduce seqtk RNG."""
    rng = random.Random(seed)
    with gzip.open(source, 'rb') as reader, gzip.open(destination, 'wb') as writer:
        while header := reader.readline():
            lines = [header] + [reader.readline() for _ in range(3)]
            if rng.random() < fraction:
                writer.write(b''.join(lines))
    log.write_text('MOCK SAMPLER NOT SEQTK')


class FractionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='brisance-fraction-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = []
        for index in range(5):
            role = 'normal' if index == 4 else 'tumor'
            paths = []
            for mate in (1, 2):
                path = self.root / f'lane{index}_R{mate}.fastq.gz'
                with gzip.open(path, 'wb') as writer:
                    for number in range(200):
                        writer.write(f'@lane{index}:{number}/{mate}\nACGTACGT\n+\nIIIIIIII\n'.encode())
                paths.append(str(path))
            self.rows.append(dict(sample='germinativo' if role == 'normal' else 'somatico',
                role=role, pair_id=f'lane{index}', fastq_1=paths[0], fastq_2=paths[1]))
        self.sheet = self.root / 'input.csv'
        self.save_rows()

    def save_rows(self):
        with self.sheet.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=HELPER.COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows)

    def prepare(self):
        with patch.object(HELPER, 'probe_tools', return_value='MOCK seqtk 1.4-r122'), \
                patch.object(HELPER, 'sample_mate', side_effect=sample_mock), \
                patch.object(HELPER.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 10 ** 15})()):
            return HELPER.prepare(self.sheet, self.root / 'output', execute=True)

    def test_dry_run_has_no_outputs_or_container_calls(self):
        with patch.object(HELPER, 'probe_tools') as probe, patch.object(HELPER, 'sample_mate') as sample:
            self.assertIsNone(HELPER.prepare(self.sheet, self.root / 'output'))
            probe.assert_not_called()
            sample.assert_not_called()
        self.assertFalse((self.root / 'output').exists())

    def test_all_five_rows_paired_manifest_and_originals_preserved(self):
        before = {row[key]: Path(row[key]).read_bytes() for row in self.rows for key in ('fastq_1', 'fastq_2')}
        result = self.prepare()
        with result.open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 5)
        self.assertEqual([row['pair_id'] for row in rows], [row['pair_id'] for row in self.rows])
        manifest = json.loads((result.parent / 'manifest.json').read_text())
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual(len(manifest['completed_pairs']), 5)
        self.assertEqual(manifest['requested_fraction'], 0.2)
        for row, entry in zip(rows, manifest['completed_pairs']):
            count, hashes = HELPER.verify_pair([Path(row['fastq_1']), Path(row['fastq_2'])])
            self.assertGreater(count, 0)
            self.assertLess(count, 200)
            self.assertEqual(entry['selected_pairs'], count)
            self.assertEqual(entry['uncompressed_output_sha256'], hashes)
        for path, data in before.items():
            self.assertEqual(Path(path).read_bytes(), data)

    def test_repeated_preparation_uses_unique_directory_and_reproduces_selection(self):
        first, second = self.prepare(), self.prepare()
        self.assertNotEqual(first.parent, second.parent)
        a = json.loads((first.parent / 'manifest.json').read_text())
        b = json.loads((second.parent / 'manifest.json').read_text())
        self.assertEqual([r['uncompressed_output_sha256'] for r in a['completed_pairs']],
                         [r['uncompressed_output_sha256'] for r in b['completed_pairs']])

    def test_seed_is_stable_distinct_between_pairs_and_changes_with_base(self):
        seeds = [HELPER.pair_seed(42, row['pair_id']) for row in self.rows]
        self.assertEqual(len(set(seeds)), 5)
        self.assertEqual(seeds[0], HELPER.pair_seed(42, 'lane0'))
        self.assertNotEqual(seeds[0], HELPER.pair_seed(43, 'lane0'))

    def test_invalid_parameters_do_not_start_sampling(self):
        for fraction in (0, 1, -0.2, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                HELPER.prepare(self.sheet, self.root / 'output', fraction=fraction)
        for seed in (0, -1, 2147483647):
            with self.assertRaises(ValueError):
                HELPER.prepare(self.sheet, self.root / 'output', seed=seed)

    def test_duplicate_pair_id_and_reused_fastq_rejected(self):
        self.rows[1]['pair_id'] = self.rows[0]['pair_id']
        self.save_rows()
        with self.assertRaisesRegex(ValueError, 'Duplicate pair_id'):
            HELPER.load_rows(self.sheet)
        self.rows[1]['pair_id'] = 'unique'
        self.rows[1]['fastq_1'] = self.rows[0]['fastq_1']
        self.save_rows()
        with self.assertRaisesRegex(ValueError, 'reused'):
            HELPER.load_rows(self.sheet)

    def test_sampler_failure_retains_partial_without_ready_samplesheet(self):
        with patch.object(HELPER, 'probe_tools', return_value='MOCK'), \
                patch.object(HELPER, 'sample_mate', side_effect=subprocess.CalledProcessError(7, ['MOCK'])), \
                patch.object(HELPER.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 10 ** 15})()):
            with self.assertRaises(RuntimeError):
                HELPER.prepare(self.sheet, self.root / 'output', execute=True)
        self.assertFalse(list((self.root / 'output').glob('*/samplesheet.csv')))
        manifest = json.loads(next((self.root / 'output').glob('*/manifest.json')).read_text())
        self.assertEqual(manifest['status'], 'failed')

    def test_mate_mismatch_stops_preparation_without_samplesheet(self):
        def bad_sample(source, destination, seed, fraction, log):
            sample_mock(source, destination, seed, fraction, log)
            if '_R2' in source.name:
                with gzip.open(destination, 'rb') as handle:
                    data = handle.read()
                with gzip.open(destination, 'wb') as handle:
                    handle.write(data.replace(b'@lane0:', b'@wrong:', 1))
        with patch.object(HELPER, 'probe_tools', return_value='MOCK'), \
                patch.object(HELPER, 'sample_mate', side_effect=bad_sample), \
                patch.object(HELPER.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 10 ** 15})()):
            with self.assertRaises(RuntimeError) as caught:
                HELPER.prepare(self.sheet, self.root / 'output', execute=True)
        self.assertIn('identifiers differ', str(caught.exception.__cause__))
        self.assertFalse(list((self.root / 'output').glob('*/samplesheet.csv')))

    def test_changed_source_is_detected_before_publishing(self):
        def changed_sample(source, destination, seed, fraction, log):
            sample_mock(source, destination, seed, fraction, log)
            info = source.stat()
            os.utime(source, ns=(info.st_atime_ns, info.st_mtime_ns + 1000000000))
        with patch.object(HELPER, 'probe_tools', return_value='MOCK'), \
                patch.object(HELPER, 'sample_mate', side_effect=changed_sample), \
                patch.object(HELPER.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 10 ** 15})()):
            with self.assertRaises(RuntimeError) as caught:
                HELPER.prepare(self.sheet, self.root / 'output', execute=True)
        self.assertIn('Source changed', str(caught.exception.__cause__))
        self.assertFalse(list((self.root / 'output').glob('*/samplesheet.csv')))

    def test_low_disk_space_stops_before_sampling(self):
        with patch.object(HELPER, 'probe_tools', return_value='MOCK'), \
                patch.object(HELPER.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 1})()), \
                patch.object(HELPER, 'sample_mate') as sample:
            with self.assertRaisesRegex(RuntimeError, 'Insufficient'):
                HELPER.prepare(self.sheet, self.root / 'output', execute=True)
            sample.assert_not_called()

    def test_mismatched_mates_and_record_counts_rejected(self):
        a, b = [Path(self.rows[0][key]) for key in ('fastq_1', 'fastq_2')]
        with gzip.open(b, 'wb') as writer:
            writer.write(b'@different/2\nACGT\n+\nIIII\n')
        with self.assertRaisesRegex(ValueError, 'identifiers differ'):
            HELPER.verify_pair([a, b])
        with gzip.open(b, 'wb') as writer:
            writer.write(b'@lane0:0/2\nACGT\n+\nIIII\n')
        with self.assertRaisesRegex(ValueError, 'different record counts'):
            HELPER.verify_pair([a, b])

    def test_truncated_gzip_and_empty_sample_rejected(self):
        a, b = [Path(self.rows[0][key]) for key in ('fastq_1', 'fastq_2')]
        b.write_bytes(b.read_bytes()[:-7])
        with self.assertRaises((EOFError, gzip.BadGzipFile)):
            HELPER.verify_pair([a, b])
        for path in (a, b):
            with gzip.open(path, 'wb'):
                pass
        with self.assertRaisesRegex(ValueError, 'no read pairs'):
            HELPER.verify_pair([a, b])

    def test_invalid_fastq_structure_length_and_mate_suffix_rejected(self):
        import io
        for data, expected in [(b'@a/1\nACGT\n+\nIII\n', 'length|mismatch'),
                               (b'@a/2\nACGT\n+\nIIII\n', 'wrong mate'),
                               (b'@a\nACGT\n+\n', 'incomplete'),
                               (b'a\nACGT\n+\nIIII\n', 'structure')]:
            with self.assertRaisesRegex(ValueError, expected):
                HELPER.record(io.BytesIO(data), 'MOCK', 1, 1)

    def test_container_command_read_only_mounts_quotas_digest_and_pipefail(self):
        source = Path(self.rows[0]['fastq_1'])
        destination = self.root / 'output.partial'
        with patch.object(HELPER.subprocess, 'run') as run:
            HELPER.sample_mate(source, destination, 42, 0.2, self.root / 'log.txt')
        command = run.call_args.args[0]
        self.assertIn(f'type=bind,source={source.parent},target=/input,readonly', command)
        self.assertIn(HELPER.IMAGE, command)
        self.assertIn('pipefail', command)
        self.assertEqual(command[command.index('--cpus') + 1], '2')
        self.assertEqual(command[command.index('--memory') + 1], '2g')
        self.assertTrue(run.call_args.kwargs['check'])

    def test_bash_pipeline_propagates_sampler_and_gzip_errors(self):
        binary_dir = self.root / 'bin'
        binary_dir.mkdir()
        seqtk = binary_dir / 'seqtk'
        seqtk.write_text('#!/bin/sh\nexit 7\n')
        seqtk.chmod(0o755)
        env = dict(os.environ, PATH=str(binary_dir) + ':' + os.environ['PATH'])
        source = Path(self.rows[0]['fastq_1'])
        args = ['/bin/bash', '-euo', 'pipefail', '-c', HELPER.SAMPLING_SCRIPT, 'mock', str(source), '42', '0.2', str(self.root / 'sample.gz')]
        result = subprocess.run(args, env=env, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        seqtk.write_text('#!/bin/sh\nexec cat\n')
        source.write_bytes(source.read_bytes()[:-7])
        result = subprocess.run(args, env=env, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'gzip:', result.stderr)


if __name__ == '__main__':
    unittest.main()
