"""Initial setup safety tests; mocked runtime/network, no Docker or scientific data."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('brisance_setup', ROOT / 'interface/setup_brisance.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='brisance-setup-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'interface').mkdir()
        (self.root / 'interface/brisance.example.ini').write_text((ROOT / 'interface/brisance.example.ini').read_text())
        self.runtime, self.settings = self.root / '.brisance', self.root / 'analysis.local.ini'
        self.java, self.nf = self.root / 'java', self.root / setup.NEXTFLOW_NAME
        self.java.write_text('fake-java\n')
        self.nf.write_text('fake-standalone-nextflow\n')
        self.java.chmod(0o700)
        self.nf.chmod(0o700)
        self.checksum = hashlib.sha256(self.nf.read_bytes()).hexdigest()
        patchers = [mock.patch.object(setup, 'ROOT', self.root),
                    mock.patch.object(setup, 'NEXTFLOW_SHA256', self.checksum),
                    mock.patch.object(setup.platform, 'system', return_value='Linux'),
                    mock.patch.object(setup.platform, 'machine', return_value='x86_64')]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.text = io.StringIO()

    def run_setup(self, *flags, consent=True, commands=None):
        def capture(command, **kwargs):
            if commands is not None:
                return commands(command, **kwargs)
            return ('openjdk version "21.0.12"' if command[0] == str(self.java)
                    else 'N E X T F L O W\nversion 26.04.6 build 12646')
        with contextlib.redirect_stdout(self.text), contextlib.redirect_stderr(self.text), \
                mock.patch.object(setup, 'capture', side_effect=capture) as probe, \
                mock.patch.object(setup, 'confirm', return_value=consent) as ask, \
                mock.patch.object(setup, 'download') as download:
            code = setup.main(['--java', str(self.java), '--nextflow', str(self.nf), *flags])
        return code, probe, ask, download

    def test_check_is_read_only_and_never_executes_nextflow_or_downloads(self):
        before = sorted(str(path) for path in self.root.rglob('*'))
        code, probe, ask, download = self.run_setup('--check')
        self.assertEqual(code, 0, self.text.getvalue())
        self.assertEqual(probe.call_args_list, [mock.call([str(self.java), '-version'])])
        ask.assert_not_called()
        download.assert_not_called()
        self.assertEqual(before, sorted(str(path) for path in self.root.rglob('*')))

    def test_cancellation_leaves_no_runtime_or_settings(self):
        code, _, _, download = self.run_setup(consent=False)
        self.assertEqual(code, 0)
        self.assertFalse(self.runtime.exists())
        self.assertFalse(self.settings.exists())
        download.assert_not_called()

    def test_installed_runtime_reused_without_download_and_explicit_paths_saved(self):
        code, probe, ask, download = self.run_setup('--no-download')
        self.assertEqual(code, 0, self.text.getvalue())
        self.assertIn('java = ' + str(self.java), self.settings.read_text())
        self.assertIn('nextflow = ' + str(self.nf), self.settings.read_text())
        self.assertIn('/data/tumor_R1.fastq.gz', self.settings.read_text())
        self.assertEqual(self.settings.stat().st_mode & 0o777, 0o600)
        self.assertEqual(ask.call_count, 1)
        download.assert_not_called()
        self.assertEqual(probe.call_count, 2)
        call = probe.call_args_list[-1]
        self.assertEqual(call.kwargs['env']['JAVA_CMD'], str(self.java))
        self.assertNotIn('JAVA_HOME', call.kwargs['env'])
        self.assertEqual(call.kwargs['env']['NXF_OFFLINE'], 'true')
        self.assertEqual(call.kwargs['env']['NXF_HOME'], str(self.runtime / 'nextflow-home'))
        record = json.loads(next(self.runtime.glob('setup-*.json')).read_text())
        self.assertEqual(record['status'], 'complete')
        self.assertFalse(record['analysis_started'])
        self.assertEqual(record['approved_downloads'], [])

    def test_repeated_setup_preserves_existing_personal_configuration(self):
        self.assertEqual(self.run_setup('--no-download')[0], 0)
        self.settings.write_text('personal settings must remain exactly as entered\n')
        before = self.settings.read_bytes()
        self.assertEqual(self.run_setup('--no-download')[0], 0, self.text.getvalue())
        self.assertEqual(self.settings.read_bytes(), before)
        self.assertEqual(len(list(self.runtime.glob('setup-*.json'))), 2)

    def test_unknown_existing_runtime_folder_is_never_adopted(self):
        self.runtime.mkdir()
        (self.runtime / 'existing.txt').write_text('untouched')
        code, probe, ask, download = self.run_setup()
        self.assertEqual(code, 1)
        probe.assert_not_called()
        ask.assert_not_called()
        download.assert_not_called()
        self.assertEqual((self.runtime / 'existing.txt').read_text(), 'untouched')

    def test_symbolic_link_runtime_or_settings_is_refused(self):
        target = self.root / 'target'
        target.mkdir()
        self.runtime.symlink_to(target, target_is_directory=True)
        self.assertEqual(self.run_setup()[0], 1)
        self.runtime.unlink()
        self.settings.symlink_to(self.root / 'missing')
        self.assertEqual(self.run_setup()[0], 1)
        self.assertFalse((target / setup.MARKER).exists())

    def test_wrong_explicit_nextflow_not_executed_or_replaced(self):
        self.nf.write_text('different-version-or-thin-launcher')
        code, probe, ask, download = self.run_setup()
        self.assertEqual(code, 1)
        self.assertEqual(probe.call_count, 1)
        ask.assert_not_called()
        download.assert_not_called()
        self.assertEqual(self.nf.read_text(), 'different-version-or-thin-launcher')

    def test_wrong_java_does_not_trigger_automatic_replacement(self):
        code, _, ask, download = self.run_setup(commands=lambda *a, **k: 'openjdk version "11.0.30"')
        self.assertEqual(code, 1)
        ask.assert_not_called()
        download.assert_not_called()

    def test_no_download_missing_runtime_leaves_nothing_written(self):
        self.nf.unlink()
        with contextlib.redirect_stdout(self.text), contextlib.redirect_stderr(self.text), \
                mock.patch.object(setup, 'select_java', return_value=(self.java, 'openjdk version "21.0.12"')), \
                mock.patch.object(setup, 'confirm') as ask, mock.patch.object(setup, 'download') as download:
            code = setup.main(['--no-download'])
        self.assertEqual(code, 1)
        ask.assert_not_called()
        download.assert_not_called()
        self.assertFalse(self.runtime.exists())

    def test_each_required_download_needs_approval_before_any_writes(self):
        with contextlib.redirect_stdout(self.text), contextlib.redirect_stderr(self.text), \
                mock.patch.object(setup, 'select_java', return_value=(None, None)), \
                mock.patch.object(setup, 'select_nextflow', return_value=None), \
                mock.patch.object(setup, 'confirm', side_effect=[True, True, False]) as ask, \
                mock.patch.object(setup, 'download') as download:
            self.assertEqual(setup.main([]), 0)
        self.assertEqual(ask.call_count, 3)
        download.assert_not_called()
        self.assertFalse(self.runtime.exists())

    def test_noninteractive_setup_cannot_consent(self):
        with mock.patch.object(setup.sys.stdin, 'isatty', return_value=False):
            with self.assertRaises(setup.SetupError):
                setup.confirm('Prepare?')

    def test_failed_nextflow_probe_records_failure_without_settings(self):
        def probe(command, **kwargs):
            if command[0] == str(self.java):
                return 'openjdk version "21.0.12"'
            raise setup.SetupError('probe failed')
        self.assertEqual(self.run_setup(commands=probe)[0], 1)
        self.assertFalse(self.settings.exists())
        record = json.loads(next(self.runtime.glob('setup-*.json')).read_text())
        self.assertEqual(record['status'], 'failed')
        self.assertEqual(record['error'], 'probe failed')
        self.assertEqual(self.nf.read_bytes(), b'fake-standalone-nextflow\n')

    def test_unsafe_destination_paths_are_refused(self):
        for value in ('/tmp/a b', '/tmp/a;bad', '/tmp/x/../y'):
            with self.assertRaises(setup.SetupError):
                setup.safe_path(value)
        for value in (self.root, self.root / 'workflow/private-runtime'):
            with self.assertRaises(setup.SetupError):
                setup.validate_destinations(value, self.settings)

    def test_unsupported_host_does_not_prepare_files(self):
        with mock.patch.object(setup.platform, 'machine', return_value='aarch64'):
            code, probe, ask, _ = self.run_setup()
        self.assertEqual(code, 1)
        probe.assert_not_called()
        ask.assert_not_called()


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='brisance-archive-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def archive(self, extra=()):
        path = self.root / 'jre.tar.gz'
        with tarfile.open(path, 'w:gz') as handle:
            java = tarfile.TarInfo('jdk/bin/java')
            java.mode, java.size = 0o4755, 4
            handle.addfile(java, io.BytesIO(b'java'))
            for name, kind, content in extra:
                info = tarfile.TarInfo(name)
                info.type = kind
                if kind == tarfile.SYMTYPE:
                    info.linkname = content
                    handle.addfile(info)
                else:
                    info.size = len(content)
                    handle.addfile(info, io.BytesIO(content))
        return path

    def test_regular_files_and_internal_legal_symlinks(self):
        archive = self.archive([('jdk/legal/java.base/LICENSE', tarfile.REGTYPE, b'license'),
                                ('jdk/legal/java.sql/LICENSE', tarfile.SYMTYPE, '../java.base/LICENSE')])
        extracted = setup.extract_jre(archive, self.root / 'out')
        self.assertEqual((extracted / 'bin/java').read_bytes(), b'java')
        self.assertEqual((extracted / 'bin/java').stat().st_mode & 0o7777, 0o755)
        self.assertEqual((extracted / 'legal/java.sql/LICENSE').read_bytes(), b'license')

    def test_traversal_absolute_device_hardlink_and_escaping_symlink_rejected(self):
        for extra in ([('../escape', tarfile.REGTYPE, b'x')], [('/absolute', tarfile.REGTYPE, b'x')],
                      [('jdk/device', tarfile.CHRTYPE, b'')], [('jdk/hard', tarfile.LNKTYPE, b'')],
                      [('jdk/link', tarfile.SYMTYPE, '../../escape')],
                      [('jdk/link', tarfile.SYMTYPE, '/tmp/escape')],
                      [('other/file', tarfile.REGTYPE, b'x')],
                      [('jdk/bin/java/child', tarfile.REGTYPE, b'x')]):
            with self.assertRaises(setup.SetupError):
                setup.extract_jre(self.archive(extra), self.root / 'out')
            self.assertFalse((self.root / 'out').exists())

    def test_existing_extraction_destination_never_modified(self):
        (self.root / 'out').mkdir()
        with self.assertRaises(setup.SetupError):
            setup.extract_jre(self.archive(), self.root / 'out')
        self.assertEqual(list((self.root / 'out').iterdir()), [])


class DownloadTests(unittest.TestCase):
    def test_download_checksum_verified_and_unknown_source_never_contacted(self):
        with tempfile.TemporaryDirectory() as name:
            destination = Path(name) / 'download'
            response = mock.MagicMock()
            response.__enter__.return_value = response
            response.geturl.return_value = 'https://release-assets.githubusercontent.com/download'
            response.read.side_effect = [b'payload', b'']
            opener = mock.Mock()
            opener.open.return_value = response
            with mock.patch.object(setup.urllib.request, 'build_opener', return_value=opener), \
                    contextlib.redirect_stdout(io.StringIO()):
                setup.download(setup.NEXTFLOW_URL, destination, hashlib.sha256(b'payload').hexdigest(), 100)
                self.assertEqual(destination.read_bytes(), b'payload')
                with self.assertRaises(setup.SetupError):
                    setup.download('https://untrusted.invalid/file', Path(name) / 'bad', '0' * 64, 100)
                self.assertEqual(opener.open.call_count, 1)

    def test_wrong_digest_or_oversized_download_is_refused(self):
        for checksum, maximum in (('0' * 64, 100), (hashlib.sha256(b'payload').hexdigest(), 2)):
            with tempfile.TemporaryDirectory() as name:
                response = mock.MagicMock()
                response.__enter__.return_value = response
                response.geturl.return_value = 'https://release-assets.githubusercontent.com/download'
                response.read.side_effect = [b'payload', b'']
                opener = mock.Mock()
                opener.open.return_value = response
                with mock.patch.object(setup.urllib.request, 'build_opener', return_value=opener), \
                        contextlib.redirect_stdout(io.StringIO()), self.assertRaises(setup.SetupError):
                    setup.download(setup.NEXTFLOW_URL, Path(name) / 'download', checksum, maximum)

    def test_https_downgrade_rejected(self):
        with self.assertRaises(setup.SetupError):
            setup.HTTPSRedirects().redirect_request(None, None, 302, '', {}, 'http://example.org/file')


if __name__ == '__main__':
    unittest.main()
