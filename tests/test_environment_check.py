"""Environment preflight with simulated tools only; never Docker/GPU/downloads."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

import test_configuration_assistant as fixture_module

cfg = fixture_module.cfg

SCRIPT = Path(__file__).resolve().parents[1] / 'interface/check_environment.py'
spec = importlib.util.spec_from_file_location('brisance_environment_check', SCRIPT)
environment = importlib.util.module_from_spec(spec)
with mock.patch.dict(sys.modules, {'configure_brisance': cfg}):
    spec.loader.exec_module(environment)


class FakeTools:
    def __init__(self, java, nextflow):
        self.java, self.nextflow = str(java), str(nextflow)
        self.calls, self.downloads = [], []
        self.missing, self.wrong = set(), set()
        self.keep_wrong_after_pull = False
        self.java_version = 'openjdk version "21.0.10-internal"\nOpenJDK Runtime Environment'
        self.nextflow_version = 'N E X T F L O W\nversion 26.04.6 build 12646'
        self.docker_endpoint = 'unix:///var/run/docker.sock'
        self.docker_version = '27.1.2'
        self.busy_gpu, self.wrong_visible, self.mig_enabled = False, False, False
        self.gpu_model = 'NVIDIA A100-SXM4-80GB'
        self.apps = 'GPU-OTHER, 999'  # Other users' GPUs must be left alone.
        self.container_failure = False
        self.inspect_permission_failure = False
        self.host_ids = [5, 6, 7]
        self.ids = {item['image']: 'sha256:' + format(i + 1, '064x') for i, item in enumerate(environment.IMAGES)}
        self.outputs = {
            environment.IMAGES[0]['image']: 'version 0.4.4\n1.13\nFastQC v0.11.5',
            environment.IMAGES[1]['image']: 'Parabricks version 4.5.1-1',
            environment.IMAGES[2]['image']: 'samtools 1.19\nUsing htslib 1.19',
            environment.IMAGES[3]['image']: 'The Genome Analysis Toolkit (GATK) v4.6.2.0',
            environment.IMAGES[4]['image']: 'bcftools 1.21\nUsing htslib 1.21',
            environment.IMAGES[5]['image']: 'Versions:\n  ensembl-vep : 113.0',
        }

    def pull(self, image):
        self.downloads.append(image)
        self.missing.discard(image)
        if not self.keep_wrong_after_pull:
            self.wrong.discard(image)
        self.ids[image] = 'sha256:' + format(100 + len(self.downloads), '064x')

    def run(self, args, env=None, timeout=None):
        self.calls.append((list(args), dict(env or {})))
        if args[0] == self.java:
            return self.java_version
        if args[0] == self.nextflow:
            return self.nextflow_version
        if args[0] == 'nvidia-smi':
            if '--query-compute-apps=gpu_uuid,pid' in args:
                return self.apps
            if '--query-gpu=index,mig.mode.current' in args:
                return '\n'.join('{}, {}'.format(i, 'Enabled' if self.mig_enabled else 'Disabled') for i in self.host_ids)
            return '\n'.join('{}, GPU-{}, {}, 81920, 81050, {}, 535.216.03'.format(
                i, i, self.gpu_model, 25 if self.busy_gpu else 0) for i in self.host_ids)
        if args[:3] == ['docker', 'context', 'inspect']:
            return self.docker_endpoint
        if args[:2] == ['docker', 'version']:
            return self.docker_version
        if args[:2] == ['docker', 'info']:
            return json.dumps({'os': 'linux', 'architecture': 'x86_64', 'root': '/var/lib/docker'})
        if args[:3] == ['docker', 'image', 'inspect']:
            image = args[3]
            if self.inspect_permission_failure:
                raise environment.CheckFailure('permission denied on Docker socket')
            if image in self.missing:
                raise environment.CheckFailure('Error: No such image: ' + image)
            return json.dumps({'id': self.ids[image], 'digests': [], 'os': 'linux', 'architecture': 'amd64'})
        if args[:2] == ['docker', 'run']:
            image_id = next((item for item in args if item.startswith('sha256:')), None)
            self.assert_fixed_image(image_id)
            command = args[args.index(image_id) + 1:]
            if self.container_failure:
                raise environment.CheckFailure('container launch failed')
            if command[0] == 'nvidia-smi':
                return 'GPU-1' if self.wrong_visible else '\n'.join('GPU-' + str(i) for i in self.host_ids)
            if command[0] == 'bash' and 'check-input-access' in command:
                return ''
            if command[0] == 'bash' and any('container-write-check.txt' in item for item in command):
                return ''
            image = next(key for key, value in self.ids.items() if value == image_id)
            return 'wrong version 999.0' if image in self.wrong else self.outputs[image]
        raise AssertionError('Unexpected external command: ' + repr(args))

    def assert_fixed_image(self, image_id):
        if image_id not in self.ids.values():
            raise AssertionError('Diagnostic containers must run the inspected immutable image ID.')


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.ConfigurationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.config = cfg.validate_configuration(self.fixture.config)
        estimate = cfg.storage_estimate(self.config)
        self.root = cfg.save_configuration(self.config, estimate, cfg.execution_summary(self.config, estimate))
        self.directory = self.root / 'reports/environment-test'
        self.directory.mkdir()
        self.java, self.nextflow = self.fixture.base / 'java', self.fixture.base / 'nextflow'
        for path in (self.java, self.nextflow):
            path.write_text('#!/bin/sh\nexit 99\n')
            path.chmod(0o700)
        self.tools = FakeTools(self.java, self.nextflow)
        self.prompt = mock.Mock(return_value=True)
        self.checker = environment.EnvironmentCheck(self.config, self.directory,
            java=str(self.java), nextflow=str(self.nextflow), runner=self.tools.run,
            downloader=self.tools.pull, ask=self.prompt)
        self.patch_host = mock.patch.object(environment, 'host_capacity', return_value={
            'system': 'Linux', 'machine': 'x86_64', 'logical_cpus_available': 256,
            'memory_available_bytes': 2 * 1024**4})
        self.patch_host.start()
        self.addCleanup(self.patch_host.stop)
        self.redirect = contextlib.redirect_stdout(io.StringIO())
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)
        self.env_patch = mock.patch.dict(os.environ, {}, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.checker.env = {'NXF_OFFLINE': 'true', 'NXF_DISABLE_CHECK_LATEST': 'true'}

    def test_complete_preflight_only_runs_diagnostics_and_no_downloads(self):
        report = self.checker.run()
        self.assertIn(report['status'], ('passed', 'passed_with_notes'))
        self.assertFalse(report['analysis_started'])
        self.assertEqual(self.tools.downloads, [])
        self.assertEqual(len(report['images']), 6)
        self.prompt.assert_not_called()
        for args, child_env in self.tools.calls:
            self.assertNotIn('--in-fq', args)
            self.assertNotIn('--ref', args)
            self.assertNotIn('--in-tumor-bam', args)
            self.assertNotIn('prune', args)
            self.assertNotIn('stop', args)
            self.assertNotIn('sudo', args)
            if args[0] == str(self.nextflow):
                self.assertEqual(child_env['JAVA_CMD'], str(self.java))
            if args[:2] == ['docker', 'run']:
                self.assertEqual(args[args.index('--pull') + 1], 'never')
                self.assertEqual(args[args.index('--network') + 1], 'none')

    def test_missing_image_downloads_once_only_after_yes(self):
        image = environment.IMAGES[4]['image']
        self.tools.missing.add(image)
        with mock.patch.object(sys.stdin, 'isatty', return_value=True):
            self.checker.run()
        self.assertEqual(self.tools.downloads, [image])
        self.prompt.assert_called_once()
        self.assertTrue(self.checker.report['downloads'][0]['approved'])
        self.assertEqual(self.checker.report['downloads'][0]['status'], 'completed')

    def test_download_cancel_stops_before_later_images(self):
        self.tools.missing.add(environment.IMAGES[0]['image'])
        self.prompt.return_value = False
        with mock.patch.object(sys.stdin, 'isatty', return_value=True), self.assertRaises(environment.Cancelled):
            self.checker.run()
        self.assertEqual(self.tools.downloads, [])
        self.assertFalse(self.checker.report['downloads'][0]['approved'])
        self.assertEqual(self.checker.images, {})

    def test_no_download_mode_never_prompts_or_downloads(self):
        self.tools.missing.add(environment.IMAGES[0]['image'])
        self.checker.allow_downloads = False
        with mock.patch.object(sys.stdin, 'isatty', return_value=True), self.assertRaises(environment.CheckFailure):
            self.checker.run()
        self.prompt.assert_not_called()
        self.assertEqual(self.tools.downloads, [])

    def test_noninteractive_missing_image_never_downloads(self):
        self.tools.missing.add(environment.IMAGES[0]['image'])
        with mock.patch.object(sys.stdin, 'isatty', return_value=False), self.assertRaises(environment.CheckFailure):
            self.checker.run()
        self.prompt.assert_not_called()
        self.assertEqual(self.tools.downloads, [])

    def test_wrong_version_refresh_is_explicit_and_rechecked(self):
        image = environment.IMAGES[4]['image']
        self.tools.wrong.add(image)
        before_id = self.tools.ids[image]
        with mock.patch.object(sys.stdin, 'isatty', return_value=True):
            self.checker.run()
        self.assertEqual(self.tools.downloads, [image])
        self.assertNotEqual(self.checker.report['images'][image]['id'], before_id)
        self.assertIn('wrong version', self.checker.report['images'][image]['previous_version_output'])
        self.assertTrue(any(item['status'] == 'failed' and 'tool version' in item['name'] for item in self.checker.report['checks']))

    def test_download_that_still_has_wrong_version_is_rejected_without_loop(self):
        self.tools.wrong.add(environment.IMAGES[0]['image'])
        self.tools.keep_wrong_after_pull = True
        with mock.patch.object(sys.stdin, 'isatty', return_value=True), self.assertRaises(environment.VersionMismatch):
            self.checker.run()
        self.assertEqual(len(self.tools.downloads), 1)

    def test_permission_failure_is_not_misreported_as_missing_image(self):
        self.tools.inspect_permission_failure = True
        with self.assertRaisesRegex(environment.CheckFailure, 'permission denied'):
            self.checker.run()
        self.prompt.assert_not_called()
        self.assertEqual(self.tools.downloads, [])

    def test_java11_and_wrong_nextflow_stop_without_system_changes(self):
        self.tools.java_version = 'openjdk version "11.0.30"'
        with self.assertRaisesRegex(environment.CheckFailure, 'Java 17'):
            self.checker.run()
        self.tools.java_version = 'openjdk version "21.0.10"'
        self.tools.nextflow_version = 'version 26.10.2 build 99999'
        with self.assertRaisesRegex(environment.CheckFailure, 'evaluated Nextflow'):
            self.checker.run()
        self.assertEqual(self.tools.downloads, [])

    def test_stale_java_home_only_removed_from_child_environment(self):
        self.checker.env['JAVA_HOME'] = '/stale/java11'
        self.checker.check_java()
        self.assertNotIn('JAVA_HOME', self.checker.env)
        self.assertEqual(self.checker.env['JAVA_CMD'], str(self.java))

    def test_remote_docker_and_old_engine_rejected(self):
        self.tools.docker_endpoint = 'ssh://remote-machine'
        with self.assertRaisesRegex(environment.CheckFailure, 'remote'):
            self.checker.check_docker()
        self.tools.docker_endpoint = 'unix:///var/run/docker.sock'
        self.tools.docker_version = '19.03.0'
        with self.assertRaisesRegex(environment.CheckFailure, '20.10'):
            self.checker.check_docker()

    def test_docker_context_override_cannot_hide_remote_endpoint(self):
        self.checker.env['DOCKER_HOST'] = 'unix:///var/run/docker.sock'
        self.checker.env['DOCKER_CONTEXT'] = 'remote-context'
        self.tools.docker_endpoint = 'ssh://remote-server'
        with self.assertRaisesRegex(environment.CheckFailure, 'remote'):
            self.checker.check_docker()
        self.assertIn('remote-context', self.tools.calls[-1][0])

    def test_busy_selected_gpu_stops_without_killing_other_jobs(self):
        self.tools.busy_gpu = True
        with self.assertRaisesRegex(environment.CheckFailure, 'appears busy'):
            self.checker.run()
        self.assertFalse(any('stop' in args or 'kill' in args for args, _ in self.tools.calls))

    def test_compute_process_on_selected_gpu_rejected_but_other_gpu_ignored(self):
        self.tools.apps = 'GPU-1, 999'
        self.assertEqual(len(self.checker.check_gpus()), 3)
        self.tools.apps = 'GPU-7, 555'
        with self.assertRaisesRegex(environment.CheckFailure, 'compute process'):
            self.checker.check_gpus()

    def test_missing_gpu_and_mig_enabled_rejected(self):
        self.tools.host_ids = [5, 7]
        with self.assertRaisesRegex(environment.CheckFailure, 'Not all'):
            self.checker.check_gpus()
        self.tools.host_ids = [5, 6, 7]
        self.tools.mig_enabled = True
        with self.assertRaisesRegex(environment.CheckFailure, 'MIG'):
            self.checker.check_gpus()

    def test_gpu_visibility_mismatch_inside_container_is_rejected(self):
        self.tools.wrong_visible = True
        with self.assertRaisesRegex(environment.CheckFailure, 'GPU identities'):
            self.checker.run()

    def test_other_gpu_models_are_not_claimed_validated(self):
        self.tools.gpu_model = 'Other NVIDIA GPU'
        self.checker.check_gpus()
        self.assertTrue(any('do not establish Parabricks support' in item for item in self.checker.report['warnings']))

    def test_input_mounts_are_read_only_and_only_probe_folder_is_writable(self):
        self.checker.run()
        mount_specs = [args[i + 1] for args, _ in self.tools.calls for i, value in enumerate(args) if value == '--mount']
        self.assertTrue(mount_specs)
        writable = [item for item in mount_specs if not item.endswith(',readonly')]
        self.assertEqual(writable, ['type=bind,source={},target=/out'.format(self.directory)])
        for args, _ in self.tools.calls:
            if 'check-input-access' in args:
                self.assertFalse(any('cat ' in item or 'gzip' in item for item in args))

    def test_insufficient_host_cpu_or_memory_fails(self):
        for changes in ({'logical_cpus_available': 64}, {'memory_available_bytes': 1024}):
            host = {'system': 'Linux', 'machine': 'x86_64', 'logical_cpus_available': 256,
                    'memory_available_bytes': 2 * 1024**4, **changes}
            with mock.patch.object(environment, 'host_capacity', return_value=host), self.assertRaises(environment.CheckFailure):
                self.checker.check_host()

    def test_low_storage_recorded_without_claiming_approval(self):
        with mock.patch.object(cfg.shutil, 'disk_usage', return_value=mock.Mock(free=0)):
            result = self.checker.check_storage()
        self.assertFalse(result['meets_recommendation'])
        self.assertTrue(any('not approval' in item for item in self.checker.report['warnings']))

    def test_diagnostic_failure_not_turned_into_download_offer(self):
        self.tools.container_failure = True
        with self.assertRaisesRegex(environment.CheckFailure, 'container launch failed'):
            self.checker.run()
        self.prompt.assert_not_called()
        self.assertEqual(self.tools.downloads, [])

    def test_main_preserves_unique_report_on_success_and_failure(self):
        original_class = environment.EnvironmentCheck
        def factory(*args, **kwargs):
            return original_class(*args, **kwargs, runner=self.tools.run, downloader=self.tools.pull, ask=self.prompt)
        command = [str(self.root / 'brisance.json'), '--java', str(self.java), '--nextflow', str(self.nextflow), '--no-download']
        with mock.patch.object(environment, 'EnvironmentCheck', side_effect=factory), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(environment.main(command), 0)
            self.tools.busy_gpu = True
            self.assertEqual(environment.main(command), 1)
        files = list((self.root / 'reports').glob('environment-*/environment.json'))
        self.assertEqual(len(files), 2)
        reports = [json.loads(path.read_text()) for path in files]
        self.assertEqual({item['status'] for item in reports}, {'passed_with_notes', 'failed'})
        self.assertTrue(all(not item['analysis_started'] for item in reports))
        self.assertEqual(list((self.root / 'work').iterdir()), [])
        self.assertEqual(list((self.root / 'results').iterdir()), [])

    def test_cli_help_does_not_contact_tools(self):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--no-download', result.stdout)

    def test_capture_nonzero_and_timeout_have_actionable_errors(self):
        result = subprocess.CompletedProcess(['missing'], 1, stdout='permission denied')
        with mock.patch.object(subprocess, 'run', return_value=result), self.assertRaisesRegex(environment.CheckFailure, 'permission denied'):
            environment.capture(['missing'])
        with mock.patch.object(subprocess, 'run', side_effect=subprocess.TimeoutExpired(['slow'], 1)), self.assertRaises(environment.CheckFailure):
            environment.capture(['slow'], timeout=1)

    def test_cleanup_only_stops_own_labelled_diagnostic(self):
        container_id = 'a' * 64
        cidfile = self.directory / 'diagnostic-test.cid'
        cidfile.write_text(container_id + '\n')
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            return self.checker.owner_label if args[1] == 'inspect' else ''
        self.checker.runner = runner
        self.checker.cleanup_diagnostic(str(cidfile))
        self.assertEqual(calls[-1], ['docker', 'stop', '--time', '5', container_id])
        calls.clear()
        self.checker.runner = lambda args, **kwargs: calls.append(args) or 'another-owner'
        self.checker.cleanup_diagnostic(str(cidfile))
        self.assertEqual(len(calls), 1)
        self.assertNotIn('stop', calls[0])

    def test_cleanup_rejects_untrusted_cid_path_or_text(self):
        calls = []
        self.checker.runner = lambda args, **kwargs: calls.append(args) or ''
        cidfile = self.directory / 'unsafe.cid'
        cidfile.write_text('all; echo unsafe\n')
        self.checker.cleanup_diagnostic(str(cidfile))
        outside = self.root / 'outside.cid'
        outside.write_text('a' * 64)
        self.checker.cleanup_diagnostic(str(outside))
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
