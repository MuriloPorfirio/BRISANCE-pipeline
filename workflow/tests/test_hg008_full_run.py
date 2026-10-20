"""Synthetic 100% launcher safety tests; no real sequencing, Docker or GPUs."""
import csv
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'hg008_full_run.py'
SPEC = importlib.util.spec_from_file_location('hg008_full_run', SOURCE)
FULL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FULL)


def snapshot(fraction=.4):
    return {'utc': 'MOCK', 'used_bytes': 1, 'available_bytes': 9,
            'used_fraction': fraction}


class FullRunTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='brisance-full-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        patcher = patch.object(FULL, 'ROOT', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.reports = self.root / 'reports/hg008-100pct/execution-abcdef'
        self.reports.mkdir(parents=True)

    def raw_fixture(self):
        expected = {}
        rows = []
        for pair_id, (sample, role, folder, old1, old2) in FULL.EXPECTED_PAIRS.items():
            expected[pair_id] = (sample, role, folder, 6, 6)
            paths = []
            for mate in (1, 2):
                path = self.root / 'data/raw' / folder / (pair_id + '_R{}_001.fastq.gz'.format(mate))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'MOCK\n\n')
                paths.append(str(path))
            rows.append([sample, role, pair_id] + paths)
        self.sheet(rows)
        return expected, rows

    def sheet(self, rows):
        with (self.root / 'hg008_samplesheet.csv').open('w', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['sample', 'role', 'pair_id', 'fastq_1', 'fastq_2'])
            writer.writerows(rows)

    def test_known_original_total(self):
        self.assertEqual(sum(row[3] + row[4] for row in FULL.EXPECTED_PAIRS.values()), 500242287130)

    def test_all_original_pairs_metadata_without_reading_fastq_bodies(self):
        expected, rows = self.raw_fixture()
        original_open = Path.open
        def small_metadata_only(path, *args, **kwargs):
            self.assertFalse(str(path).endswith('.fastq.gz'), 'FASTQ content must not be opened')
            return original_open(path, *args, **kwargs)
        with patch.object(FULL, 'EXPECTED_PAIRS', expected), patch.object(Path, 'open', small_metadata_only):
            data = FULL.raw_metadata()
        self.assertEqual(data['pairs'], 5)
        self.assertEqual(len(data['files']), 10)
        self.assertEqual(data['source_bytes'], 60)

    def test_subsample_path_refused(self):
        expected, rows = self.raw_fixture()
        rows[0][3] = str(self.root / 'data/subsample/file.fastq.gz')
        self.sheet(rows)
        with patch.object(FULL, 'EXPECTED_PAIRS', expected):
            with self.assertRaisesRegex(ValueError, 'diretamente para os originais'):
                FULL.raw_metadata()

    def test_wrong_size_refused(self):
        expected, rows = self.raw_fixture()
        Path(rows[0][3]).write_bytes(b'changed')
        with patch.object(FULL, 'EXPECTED_PAIRS', expected):
            with self.assertRaisesRegex(ValueError, 'tamanho diferente'):
                FULL.raw_metadata()

    def test_duplicate_pair_refused(self):
        expected, rows = self.raw_fixture()
        rows[1] = rows[0]
        self.sheet(rows)
        with patch.object(FULL, 'EXPECTED_PAIRS', expected):
            with self.assertRaisesRegex(ValueError, 'cinco pares originais'):
                FULL.raw_metadata()

    def test_existing_output_preserved(self):
        output = self.root / 'results/hg008-100pct'
        output.mkdir(parents=True)
        sentinel = output / 'KEEP.txt'
        sentinel.write_text('USER-OWNED MOCK')
        with self.assertRaisesRegex(ValueError, 'Já existe'):
            FULL.check_paths()
        self.assertEqual(sentinel.read_text(), 'USER-OWNED MOCK')

    def test_broken_work_link_refused(self):
        work = self.root / 'work'
        work.mkdir()
        (work / 'hg008-100pct').symlink_to(self.root / 'missing')
        with self.assertRaisesRegex(ValueError, 'Já existe'):
            FULL.check_paths()

    def test_storage_uses_nonroot_available_blocks(self):
        values = SimpleNamespace(f_blocks=1000, f_bfree=500, f_bavail=450, f_frsize=4096)
        with patch.object(FULL.os, 'statvfs', return_value=values):
            data = FULL.storage()
        self.assertEqual(data['used_bytes'], 500 * 4096)
        self.assertAlmostEqual(data['used_fraction'], 500 / 950)
        self.assertNotIn('headroom_to_60_bytes', data)

    def test_no_initial_headroom_requirement_accepts_above_60(self):
        for fraction in (.537, .60, .62, .63999):
            FULL.require_storage(snapshot(fraction))
        self.assertEqual(FULL.LIMIT, .65)
        self.assertFalse(hasattr(FULL, 'START_HEADROOM'))

    def test_runtime_stops_at_64_before_65(self):
        FULL.require_storage(snapshot(.63999))
        with self.assertRaisesRegex(ValueError, 'interrupção'):
            FULL.require_storage(snapshot(.64))
        with self.assertRaisesRegex(ValueError, '65%'):
            FULL.require_storage(snapshot(.65))

    def gpu_output(self, used=False, utilization=0):
        gpu_rows = '\n'.join('{}, GPU-{}, NVIDIA A100-SXM4-80GB, 81920, {}, {}'.format(
            number, number, 100 if used else 81050, utilization) for number in ('5', '6', '7'))
        return [gpu_rows, '']

    def test_idle_selected_gpus_accepted(self):
        with patch.object(FULL, 'capture', side_effect=self.gpu_output()):
            data = FULL.idle_gpus(('7', '6', '5'))
        self.assertEqual([gpu['index'] for gpu in data], ['7', '6', '5'])

    def test_busy_gpu_refused(self):
        with patch.object(FULL, 'capture', side_effect=self.gpu_output(used=True)):
            with self.assertRaisesRegex(ValueError, 'ocupada'):
                FULL.idle_gpus(('7', '6', '5'))

    def test_selected_compute_process_refused_even_if_util_zero(self):
        values = self.gpu_output()
        values[1] = 'GPU-7, 12345'
        with patch.object(FULL, 'capture', side_effect=values):
            with self.assertRaisesRegex(ValueError, 'Há um processo'):
                FULL.idle_gpus(('7', '6', '5'))

    def test_gpu_one_in_use_is_ignored(self):
        values = self.gpu_output()
        values[1] = 'GPU-1, 12345'
        with patch.object(FULL, 'capture', side_effect=values):
            self.assertEqual(len(FULL.idle_gpus(('7', '6', '5'))), 3)

    def test_stage_guard_checks_disk_and_only_requested_gpus(self):
        with patch.object(FULL, 'storage', return_value=snapshot()), patch.object(FULL, 'idle_gpus') as gpus:
            FULL.stage_guard(('7',))
            gpus.assert_called_once_with(('7',))
            gpus.reset_mock()
            FULL.stage_guard(())
            gpus.assert_not_called()

    def test_guard_config_has_only_beforescript_no_resource_or_science_changes(self):
        path = self.reports / 'safety.config'
        FULL.guard_config(path)
        text = path.read_text()
        self.assertEqual(text.count('beforeScript ='), 11)
        for forbidden in ('cpus =', 'memory =', 'container =', 'script =', 'cleanup', 'rm -'):
            self.assertNotIn(forbidden, text)

    def test_full_command_not_sampling_or_resume(self):
        command = FULL.nf_command('finalize', self.reports / 'nextflow.log',
                                  self.root / 'work/hg008-100pct', self.reports / 'safety.config', self.reports)
        self.assertEqual(command[command.index('--input') + 1], str(self.root / 'hg008_samplesheet.csv'))
        self.assertNotIn('-resume', command)
        self.assertFalse(any('20pct' in word for word in command))
        self.assertEqual(command[command.index('--gpu_devices') + 1], '7,6,5')
        self.assertEqual(command[command.index('--caller_gpu_devices') + 1], '7,6')
        self.assertIn('-with-trace', command)

    def test_archive_excludes_raw_data(self):
        self.raw_fixture()
        workflow = self.root / 'workflow'
        workflow.mkdir()
        (workflow / 'main.nf').write_text('// MOCK')
        (self.root / 'nextflow-26.04.6-dist').write_text('MOCK EXECUTABLE')
        (self.reports / 'launcher-safety.config').write_text('// MOCK')
        FULL.archive_inputs(self.reports)
        with tarfile.open(self.reports / 'execution-inputs.tar.gz') as archive:
            names = archive.getnames()
        self.assertIn('workflow/main.nf', names)
        self.assertIn('hg008_samplesheet.csv', names)
        self.assertFalse(any(name.endswith('.fastq.gz') for name in names))

    def test_monitor_success_and_logging(self):
        with patch.object(FULL, 'storage', return_value=snapshot()):
            status = FULL.monitor([sys.executable, '-c', 'pass'], self.reports, interval=.01)
        self.assertEqual(status, 0)
        self.assertTrue((self.reports / 'disk-usage.tsv').is_file())
        self.assertFalse((self.reports / 'interruption.json').exists())

    def test_monitor_preserves_failure_exit(self):
        with patch.object(FULL, 'storage', return_value=snapshot()):
            status = FULL.monitor([sys.executable, '-c', 'raise SystemExit(11)'], self.reports, interval=.01)
        self.assertEqual(status, 11)

    def test_monitor_requests_term_only_for_own_child_on_capacity(self):
        with patch.object(FULL, 'storage', return_value=snapshot(.64)):
            status = FULL.monitor([sys.executable, '-c', 'import time; time.sleep(30)'], self.reports, interval=.01)
        self.assertEqual(status, 88)
        record = json.loads((self.reports / 'nextflow-exit.json').read_text())
        self.assertTrue(record['interruption'])
        self.assertEqual(record['nextflow_exit'], -signal.SIGTERM)

    def test_monitor_failure_also_requests_stop(self):
        with patch.object(FULL, 'storage', side_effect=OSError('MOCK filesystem unavailable')):
            status = FULL.monitor([sys.executable, '-c', 'import time; time.sleep(30)'], self.reports, interval=.01)
        self.assertEqual(status, 88)

    def mock_preflight_capture(self, command, timeout=45):
        if command[-1] == '-version':
            return 'N E X T F L O W\n version 26.04.6 build MOCK'
        if command[:2] == ['docker', 'version']:
            return '27-MOCK'
        if command[:3] == ['docker', 'image', 'inspect']:
            return '{"id":"MOCK_IMAGE","digests":["MOCK_DIGEST"]}'
        if command[:2] == ['docker', 'run'] and command[-1] == '--format=csv,noheader':
            return 'GPU-7\nGPU-6\nGPU-5'
        if command[:2] == ['docker', 'run'] and command[-2] == '-c':
            return 'species homo_sapiens\nassembly GRCh38'
        raise AssertionError('Unexpected external command: ' + str(command))

    def preflight_patches(self, capacity):
        original_open = Path.open
        def fake_meminfo(path, *args, **kwargs):
            if str(path) == '/proc/meminfo':
                return io.StringIO('MemAvailable: 2000000000 kB\n')
            return original_open(path, *args, **kwargs)
        gpus = [{'uuid': 'GPU-' + index} for index in ('7', '6', '5')]
        return (patch.object(FULL, 'capture', side_effect=self.mock_preflight_capture),
                patch.object(FULL, 'idle_gpus', return_value=gpus),
                patch.object(FULL, 'storage', return_value=capacity),
                patch.object(FULL.subprocess, 'run'),
                patch.object(Path, 'open', fake_meminfo))

    def test_preflight_runs_metadata_validation_without_scientific_run(self):
        expected, _ = self.raw_fixture()
        a, b, c, d, e = self.preflight_patches(snapshot())
        with patch.object(FULL, 'EXPECTED_PAIRS', expected), a, b, c, d as run, e:
            data = FULL.preflight(self.reports)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index('--mode') + 1], 'validate-annotate')
        self.assertEqual(data['raw']['pairs'], 5)
        self.assertEqual(len(data['images']), 6)
        self.assertFalse((self.root / 'results').exists())
        self.assertFalse((self.root / 'work').exists())

    def test_preflight_at_stop_threshold_prevents_full_execution(self):
        expected, _ = self.raw_fixture()
        a, b, c, d, e = self.preflight_patches(snapshot(.64))
        with patch.object(FULL, 'EXPECTED_PAIRS', expected), a, b, c, d, e, \
                patch.object(FULL.subprocess, 'Popen') as process:
            with self.assertRaisesRegex(ValueError, '64%'):
                FULL.preflight(self.reports)
        process.assert_not_called()

    def test_monitor_sends_stop_even_if_interruption_log_cannot_be_written(self):
        original_write = Path.write_text
        def unwritable_marker(path, *args, **kwargs):
            if path.name == 'interruption.json':
                raise OSError('MOCK disk write failure')
            return original_write(path, *args, **kwargs)
        with patch.object(FULL, 'storage', return_value=snapshot(.64)), \
                patch.object(Path, 'write_text', unwritable_marker):
            status = FULL.monitor([sys.executable, '-c', 'import time; time.sleep(30)'], self.reports, interval=.01)
        self.assertEqual(status, 88)


if __name__ == '__main__':
    unittest.main()
