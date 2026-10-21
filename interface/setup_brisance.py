#!/usr/bin/env python3
"""Prepare a private Java/Nextflow runtime and editable settings; never run analysis."""

import argparse
import configparser
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import posixpath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
NEXTFLOW_VERSION = '26.04.6'
NEXTFLOW_NAME = 'nextflow-26.04.6-dist'
NEXTFLOW_URL = 'https://github.com/nextflow-io/nextflow/releases/download/v26.04.6/' + NEXTFLOW_NAME
NEXTFLOW_SHA256 = '182a63c74074e2dc7956ffa3c8cd59de952ed2c44394e21faf5e1736b945444c'
JAVA_RELEASE = '21.0.12.1+1'
JAVA_URL = ('https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/'
            'OpenJDK21U-jre_x64_linux_hotspot_21.0.12.1_1.tar.gz')
JAVA_SHA256 = '2413149700df0f7d440500a84a8f764c535f21e5a5e87d38328b64eec2c5b500'
JAVA_FOLDER = 'temurin-' + JAVA_RELEASE + '-jre'
MARKER = '.brisance-runtime.json'


class SetupError(RuntimeError):
    pass


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def safe_path(value):
    path = Path(value).absolute()
    if not re.fullmatch(r'/[A-Za-z0-9_./+\-]+', str(path)) or '..' in path.parts:
        raise SetupError('Use an absolute path without spaces or shell characters: ' + str(path))
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise SetupError('Setup destinations must not contain symbolic links: ' + str(ancestor))
    return path


def capture(command, env=None, cwd=None):
    try:
        result = subprocess.run(command, env=env, cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors='replace', timeout=90)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SetupError('Could not execute {}: {}'.format(command[0], exc)) from exc
    if result.returncode:
        raise SetupError('{} exited {}: {}'.format(command[0], result.returncode, result.stdout[-2000:]))
    return result.stdout.strip()


def executable(value):
    if not value:
        return None
    path = Path(value) if '/' in str(value) else Path(shutil.which(str(value)) or '/nonexistent')
    return path.resolve() if path.is_file() and os.access(path, os.X_OK) else None


def select_java(explicit, runtime):
    candidates = [explicit] if explicit else [runtime / JAVA_FOLDER / 'bin/java', os.environ.get('JAVA_CMD'),
        str(Path(os.environ['JAVA_HOME']) / 'bin/java') if os.environ.get('JAVA_HOME') else None, 'java']
    for value in candidates:
        path = executable(value)
        if path is None:
            if explicit:
                raise SetupError('Selected Java executable was not found: ' + str(explicit))
            continue
        try:
            output = capture([str(path), '-version'])
            match = re.search(r'(?:openjdk|java) version "(\d+)(?:[.\-"+])', output)
            if match and 17 <= int(match.group(1)) <= 26:
                return path, output
        except SetupError:
            if explicit:
                raise
        if explicit:
            raise SetupError('Selected Java must be version 17–26. Other Java installations were not changed.')
    return None, None


def select_nextflow(explicit, runtime):
    candidates = [explicit] if explicit else [runtime / NEXTFLOW_NAME, ROOT / NEXTFLOW_NAME,
                                             shutil.which('nextflow')]
    for value in candidates:
        path = executable(value)
        if path is None:
            if explicit:
                raise SetupError('Selected Nextflow executable was not found: ' + str(explicit))
            continue
        if digest(path) == NEXTFLOW_SHA256:
            return path
        if explicit or path == runtime / NEXTFLOW_NAME:
            raise SetupError('Selected Nextflow is not the verified standalone {} distribution. '
                             'Use its -dist file; existing installations are never replaced.'.format(NEXTFLOW_VERSION))
        # Do not execute unrecognized/thin launchers: they may download code even for -version.
    return None


class HTTPSRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != 'https':
            raise SetupError('Refusing a download redirect outside HTTPS.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, destination, sha256, maximum_bytes):
    """Exclusive staging file, HTTPS only, bounded download and mandatory SHA-256."""
    if url not in (JAVA_URL, NEXTFLOW_URL):
        raise SetupError('Unknown download source.')
    opener = urllib.request.build_opener(HTTPSRedirects())
    request = urllib.request.Request(url, headers={'User-Agent': 'BRISANCE-setup'})
    start, last, size = time.monotonic(), 0, 0
    print('Downloading: ' + url, flush=True)
    with opener.open(request, timeout=30) as response, Path(destination).open('xb') as output:
        if urllib.parse.urlsplit(response.geturl()).scheme != 'https':
            raise SetupError('Download did not use HTTPS.')
        for block in iter(lambda: response.read(1024 * 1024), b''):
            size += len(block)
            if size > maximum_bytes or time.monotonic() - start > 900:
                raise SetupError('Download exceeded the size/time limit. Nothing was installed.')
            output.write(block)
            if time.monotonic() - last >= 2:
                print('  {:.1f} MiB received'.format(size / 1024**2), flush=True)
                last = time.monotonic()
    if digest(destination) != sha256:
        raise SetupError('SHA-256 mismatch. The downloaded file will not be installed or executed.')
    print('Download SHA-256: OK', flush=True)


def extract_jre(archive, destination):
    """Extract only directories/files and internal file symlinks in a new owned folder."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise SetupError('Extraction destination already exists.')
    with tarfile.open(archive, 'r:gz') as bundle:
        members = bundle.getmembers()
        if not members or len(members) > 10000 or sum(item.size for item in members) > 512 * 1024**2:
            raise SetupError('Unexpected Java archive size or member count.')
        records = {}
        for item in members:
            name = PurePosixPath(item.name)
            if name.is_absolute() or '..' in name.parts or not name.parts or '\\' in item.name:
                raise SetupError('Unsafe path in Java archive.')
            key = str(name)
            if key in records or not (item.isdir() or item.isfile() or item.issym()):
                raise SetupError('Duplicate or unsupported Java archive member.')
            records[key] = item
        prefixes = {PurePosixPath(key).parts[0] for key in records}
        if len(prefixes) != 1:
            raise SetupError('Java archive must contain one root folder.')
        prefix = prefixes.pop()
        for key, item in records.items():
            if any(str(parent) in records and not records[str(parent)].isdir()
                   for parent in PurePosixPath(key).parents if str(parent) != '.'):
                raise SetupError('Non-directory ancestor in Java archive.')
            if item.issym():
                target = posixpath.normpath(posixpath.join(str(PurePosixPath(key).parent), item.linkname))
                if (PurePosixPath(item.linkname).is_absolute() or '\\' in item.linkname
                        or not target.startswith(prefix + '/') or target not in records
                        or not records[target].isfile()):
                    raise SetupError('Unsafe Java archive link.')
        if prefix + '/bin/java' not in records or not records[prefix + '/bin/java'].isfile():
            raise SetupError('Java executable missing from archive.')
        destination.mkdir(mode=0o700)
        for key, item in records.items():
            path = destination.joinpath(*PurePosixPath(key).parts)
            if item.isdir():
                path.mkdir(parents=True, exist_ok=True)
            elif item.isfile():
                path.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(item) as source, path.open('xb') as output:
                    shutil.copyfileobj(source, output)
                path.chmod(0o755 if item.mode & 0o111 else 0o644)
        for key, item in records.items():
            if item.issym():
                path = destination.joinpath(*PurePosixPath(key).parts)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(item.linkname)
    return destination / prefix


def confirm(message):
    if not sys.stdin.isatty():
        raise SetupError('Setup needs an interactive terminal for consent. No unattended downloads or setup.')
    return input(message + ' [y/N]: ').strip().lower() in ('y', 'yes')


def render_settings(java, nextflow):
    template = (ROOT / 'interface/brisance.example.ini').read_text()
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(template)
    if 'java' not in parser['runtime'] or 'nextflow' not in parser['runtime']:
        raise SetupError('Runtime fields are missing from the bundled settings template.')
    # Preserve the template's instructions, especially multi-lane/adapters examples.
    head, runtime = template.split('[runtime]\n', 1)
    for name, value in (('java', java), ('nextflow', nextflow)):
        runtime = re.sub(r'^' + name + r'[ \t]*=[ \t]*.*$', lambda match: name + ' = ' + str(value), runtime, flags=re.M)
    return head + '[runtime]\n' + runtime


def validate_destinations(runtime, settings):
    protected = {Path('/'), Path('/tmp'), Path.home(), ROOT}
    if runtime in protected or settings == runtime or runtime in settings.parents:
        raise SetupError('Choose a dedicated runtime folder and a settings file outside it.')
    for name in ('workflow', 'pipeline', 'interface', '.git', 'provenance'):
        protected_path = ROOT / name
        if runtime == protected_path or protected_path in runtime.parents:
            raise SetupError('Do not install a runtime inside source/provenance directories.')
        if settings == protected_path or protected_path in settings.parents:
            raise SetupError('Save personal settings outside source/provenance directories.')
    if runtime.exists():
        marker = runtime / MARKER
        if not runtime.is_dir() or marker.is_symlink() or not marker.is_file():
            raise SetupError('Existing runtime folder is not managed by BRISANCE. Choose a new folder.')
        if json.loads(marker.read_text()) != {'format': 'brisance-runtime', 'schema_version': 1}:
            raise SetupError('Unrecognized runtime marker. Nothing will be replaced.')
    elif not runtime.parent.is_dir():
        raise SetupError('The runtime parent folder must already exist.')
    if not settings.parent.is_dir() or (settings.exists() and not settings.is_file()):
        raise SetupError('Settings need an existing parent and a regular file or new filename.')
    if not settings.name.endswith('.local.ini'):
        raise SetupError('Use a personal settings filename ending in .local.ini (excluded from Git).')
    for name in (JAVA_FOLDER, 'nextflow-home', 'capsule', '.setup.lock'):
        path = runtime / name
        if path.is_symlink():
            raise SetupError('Managed runtime entry must not be a symbolic link: ' + str(path))


def prepare(args):
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise SetupError('This setup supports Linux x86_64. No system changes were made.')
    runtime = safe_path(args.runtime_dir or ROOT / '.brisance')
    settings = safe_path(args.settings or ROOT / 'analysis.local.ini')
    validate_destinations(runtime, settings)
    java, java_output = select_java(args.java, runtime)
    nextflow = select_nextflow(args.nextflow, runtime)
    print('BRISANCE — initial setup\n')
    print('Runtime folder: ' + str(runtime))
    print('Java: ' + (str(java) if java else 'download required: Eclipse Temurin JRE ' + JAVA_RELEASE))
    print('Nextflow: ' + (str(nextflow) if nextflow else 'download required: standalone ' + NEXTFLOW_VERSION))
    print('Settings: {} ({})'.format(settings, 'existing file; will NOT be changed' if settings.exists() else 'new editable template'))
    print('No analysis, container downloads, driver/Docker installation, Conda activation or system changes.')
    if args.check:
        print('\nSETUP CHECK ONLY. No files written or network requests made. '
              + ('Nextflow distribution checked by SHA-256, not executed. ' if nextflow else 'Nextflow still needs to be prepared. ')
              + 'Hardware is not certified.')
        return 0
    if args.no_download and (java is None or nextflow is None):
        raise SetupError('Required runtime is missing and --no-download was selected. Provide --java and --nextflow.')
    if not confirm('Prepare this local runtime and settings template?'):
        print('Cancelled. No files written or downloads started.')
        return 0
    approvals = []
    for needed, label, url, checksum in ((java is None, 'Java ' + JAVA_RELEASE, JAVA_URL, JAVA_SHA256),
                                         (nextflow is None, 'Nextflow ' + NEXTFLOW_VERSION, NEXTFLOW_URL, NEXTFLOW_SHA256)):
        if needed:
            print('\n{}\nSource: {}\nSHA-256: {}'.format(label, url, checksum))
            if not confirm('Download this package?'):
                print('Cancelled. No files written or downloads started.')
                return 0
            approvals.append({'package': label, 'url': url, 'sha256': checksum})
    # Collect all approvals before any mutation. Existing files are never overwritten.
    validate_destinations(runtime, settings)
    if not runtime.exists():
        runtime.mkdir(mode=0o700)
        with (runtime / MARKER).open('x') as handle:
            json.dump({'format': 'brisance-runtime', 'schema_version': 1}, handle)
    lock_fd = os.open(str(runtime / '.setup.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'r+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SetupError('Another setup is using this runtime folder.') from exc
        report = {'started_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'status': 'running', 'analysis_started': False, 'approved_downloads': approvals,
                  'settings': str(settings), 'settings_created': False, 'runtime': str(runtime)}
        try:
            with tempfile.TemporaryDirectory(prefix='setup-stage-', dir=runtime) as staging:
                stage = Path(staging)
                if java is None:
                    target = runtime / JAVA_FOLDER
                    if target.exists() or target.is_symlink():
                        raise SetupError('Java target already exists but is not usable. Choose a new runtime folder.')
                    archive = stage / 'java.tar.gz'
                    download(JAVA_URL, archive, JAVA_SHA256, 100 * 1024**2)
                    extracted = extract_jre(archive, stage / 'unpacked')
                    selected, java_output = select_java(str(extracted / 'bin/java'), runtime)
                    if not re.search(r'version "21[.\-"+]', java_output):
                        raise SetupError('Downloaded Java is not version 21.')
                    if target.exists() or target.is_symlink():
                        raise SetupError('Java destination changed during setup. Nothing was replaced.')
                    extracted.rename(target)
                    java = target / 'bin/java'
                if nextflow is None:
                    target = runtime / NEXTFLOW_NAME
                    downloaded = stage / NEXTFLOW_NAME
                    download(NEXTFLOW_URL, downloaded, NEXTFLOW_SHA256, 80 * 1024**2)
                    downloaded.chmod(0o755)
                    # link() fails on an existing destination, unlike replace()/rename().
                    os.link(str(downloaded), str(target))
                    nextflow = target
                if digest(nextflow) != NEXTFLOW_SHA256:
                    raise SetupError('Nextflow distribution changed during setup.')
                env = dict(os.environ)
                env.pop('JAVA_HOME', None)
                env.update(JAVA_CMD=str(java), NXF_HOME=str(runtime / 'nextflow-home'),
                           CAPSULE_CACHE_DIR=str(runtime / 'capsule'), NXF_OFFLINE='true',
                           NXF_DISABLE_CHECK_LATEST='true')
                output = capture([str(nextflow), '-version'], env=env, cwd=str(stage))
                if not re.search(r'\bversion\s+' + re.escape(NEXTFLOW_VERSION) + r'(?=\s|$)', output):
                    raise SetupError('Nextflow version check failed.')
                report.update(java={'executable': str(java), 'version_output': java_output},
                              nextflow={'executable': str(nextflow), 'sha256': NEXTFLOW_SHA256, 'version_output': output})
                if not settings.exists() and not settings.is_symlink():
                    with settings.open('x') as handle:
                        handle.write(render_settings(java, nextflow))
                    settings.chmod(0o600)
                    report['settings_created'] = True
                report['status'] = 'complete'
        except BaseException as exc:
            report.update(status='failed', error=str(exc) or type(exc).__name__)
            raise
        finally:
            report['finished_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            with tempfile.NamedTemporaryFile(mode='w', prefix='setup-', suffix='.json', dir=runtime, delete=False) as handle:
                json.dump(report, handle, indent=2)
                handle.write('\n')
                print('Setup record: ' + handle.name)
    print('\nRUNTIME READY. No sequencing data processed.')
    print('Edit the inputs, references, GPU indices and resource limits in: ' + str(settings))
    if not report['settings_created']:
        print('Existing settings were preserved. Set [runtime] java and nextflow to these paths if necessary:')
        print('  java = ' + str(java) + '\n  nextflow = ' + str(nextflow))
    runner = ROOT / 'interface/run_brisance.sh'
    print('\nNext: bash {} {} --check'.format(runner, settings))
    print('Then: bash {} {} --run'.format(runner, settings))
    print('Docker/NVIDIA compatibility and image versions are checked later, after storage approval.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Read-only plan; no downloads, writes or Nextflow execution.')
    parser.add_argument('--no-download', action='store_true', help='Reuse installed compatible runtime only.')
    parser.add_argument('--java', help='Existing Java executable (17–26).')
    parser.add_argument('--nextflow', help='Existing verified Nextflow 26.04.6 standalone -dist executable.')
    parser.add_argument('--runtime-dir', help='New/private managed directory; default: repository/.brisance.')
    parser.add_argument('--settings', help='New personal .local.ini file; existing files are preserved.')
    args = parser.parse_args(argv)
    if sys.version_info < (3, 8):
        print('Python 3.8 or later is required.', file=sys.stderr)
        return 1
    try:
        return prepare(args)
    except (SetupError, OSError, ValueError, tarfile.TarError, EOFError) as exc:
        print('SETUP STOPPED: ' + str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nSetup interrupted. Existing settings/system installations were not changed.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
