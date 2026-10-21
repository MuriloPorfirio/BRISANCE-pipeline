#!/usr/bin/env python3
"""Check a configured BRISANCE environment. Never start a scientific analysis."""

import argparse
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import configure_brisance as configuration


NEXTFLOW_VERSION = '26.04.6'
IMAGES = (
    {'name': 'Trim Galore / Cutadapt / FastQC', 'image': 'biowardrobe2/trimgalore:v0.4.4',
     'command': ['bash', '-euc', 'trim_galore --version; cutadapt --version; fastqc --version'],
     'patterns': [r'\bversion\s+0\.4\.4\b', r'^1\.13\s*$', r'FastQC v0\.11\.5\b']},
    {'name': 'NVIDIA Parabricks', 'image': 'nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1',
     'command': ['pbrun', 'fq2bam', '--version'], 'patterns': [r'\b4\.5\.1-1\b'], 'gpu': True},
    {'name': 'SAMtools', 'image': 'staphb/samtools:1.19',
     'command': ['samtools', '--version'], 'patterns': [r'^samtools 1\.19\s*$']},
    {'name': 'GATK', 'image': 'broadinstitute/gatk:4.6.2.0',
     'command': ['gatk', '--version'], 'patterns': [r'\(GATK\)\s+v?4\.6\.2\.0\b']},
    {'name': 'BCFtools / HTSlib', 'image': 'staphb/bcftools:1.21',
     'command': ['bcftools', '--version'], 'patterns': [r'^bcftools 1\.21\s*$', r'\bhtslib 1\.21\s*$']},
    {'name': 'Ensembl VEP', 'image': 'ensemblorg/ensembl-vep:release_113.0',
     'command': ['vep', '--help'], 'patterns': [r'ensembl-vep\s*:\s*113\.0\s*$']},
)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class CheckFailure(RuntimeError):
    pass


class Cancelled(CheckFailure):
    pass


class ImageMissing(CheckFailure):
    pass


class VersionMismatch(CheckFailure):
    def __init__(self, output):
        super().__init__('Installed tool version does not match the BRISANCE image specification.')
        self.output = output


class Progress:
    """Spinner on terminals; ordinary lines in redirected logs."""

    def __init__(self, label):
        self.label = label
        self.stop = threading.Event()
        self.thread = None

    def __enter__(self):
        if sys.stdout.isatty():
            def spin():
                tick = 0
                while not self.stop.wait(0.12):
                    print('\r[{}] {}...'.format('|/-\\'[tick % 4], self.label), end='', flush=True)
                    tick += 1
            self.thread = threading.Thread(target=spin, daemon=True)
            self.thread.start()
        else:
            print('Checking: ' + self.label, flush=True)
        return self

    def __exit__(self, kind, value, traceback):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1)
        print(('\r' if self.thread else '') + ('[OK] ' if kind is None else '[FAILED] ') + self.label, flush=True)


def capture(command, env=None, timeout=60):
    """Execute fixed argument lists, never a user-supplied shell command."""
    try:
        result = subprocess.run(command, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors='replace', timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CheckFailure('{}: {}'.format(command[0], exc)) from exc
    if result.returncode:
        raise CheckFailure('{} exited {}: {}'.format(command[0], result.returncode, result.stdout[-4000:].strip()))
    return result.stdout.strip()


def pull_image(image):
    # Foreground Docker progress is visible. Pull only this exact, approved tag.
    print('Downloading {} (stored by Docker, not in the analysis folder)...'.format(image), flush=True)
    try:
        result = subprocess.run(['docker', 'pull', image], timeout=7200)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CheckFailure('Image download failed: ' + str(exc)) from exc
    if result.returncode:
        raise CheckFailure('Image download failed (exit {}). Existing images were not removed.'.format(result.returncode))


def host_capacity():
    try:
        cpus = len(os.sched_getaffinity(0))
    except AttributeError:
        cpus = os.cpu_count() or 1
    fields = {}
    with Path('/proc/meminfo').open() as handle:
        for line in handle:
            name, value = line.split(':', 1)
            fields[name] = int(value.split()[0]) * 1024
    return {'system': platform.system(), 'machine': platform.machine(),
            'logical_cpus_available': cpus, 'memory_available_bytes': fields['MemAvailable']}


def find_executable(explicit, candidates, label):
    for value in ([explicit] if explicit else candidates):
        if not value:
            continue
        value = str(value)
        path = Path(value) if '/' in value else Path(shutil.which(value) or '/nonexistent')
        if path.is_file() and os.access(path, os.X_OK):
            return str(path.resolve())
    raise CheckFailure('{} not found. Select an installed executable or activate its environment. Nothing will be installed automatically.'.format(label))


class EnvironmentCheck:
    def __init__(self, config, directory, java=None, nextflow=None, allow_downloads=True,
                 runner=capture, downloader=pull_image, ask=None):
        self.config, self.directory = config, Path(directory)
        self.java_path, self.nextflow_path = java, nextflow
        self.allow_downloads = allow_downloads
        self.runner, self.downloader = runner, downloader
        self.ask = configuration.yes_no if ask is None else ask
        self.env = dict(os.environ)
        self.env.update({'NXF_OFFLINE': 'true', 'NXF_DISABLE_CHECK_LATEST': 'true'})
        self.images = {}
        self.gpus = []
        self.container_counter = 0
        self.owner_label = self.directory.name
        self.report = {'started_at_utc': utc(), 'status': 'running', 'analysis_started': False,
                       'checks': [], 'downloads': [], 'images': {}, 'warnings': [],
                       'limitations': ['No scientific processing or CUDA-kernel benchmark is performed.',
                                       'File/index contents and reference/known-sites build compatibility are not verified.',
                                       'Resource observations are not reservations; quotas may further restrict capacity.',
                                       'This checker alone does not start analysis; the fixed runner requires --run and a separate confirmation.']}

    def run_command(self, args, timeout=60):
        try:
            return self.runner(args, env=self.env, timeout=timeout)
        except (CheckFailure, KeyboardInterrupt):
            if args[:2] == ['docker', 'run'] and '--cidfile' in args:
                self.cleanup_diagnostic(args[args.index('--cidfile') + 1])
            raise

    def cleanup_diagnostic(self, cidfile):
        """Stop only this check's labelled version/access probe after failure."""
        path = Path(cidfile)
        if path.parent != self.directory or not path.is_file() or path.is_symlink():
            return
        try:
            container_id = path.read_text().strip()
        except OSError:
            self.warn('A diagnostic ID file could not be read; no container was stopped.')
            return
        if not re.fullmatch(r'[0-9a-f]{64}', container_id):
            return
        try:
            owner = self.runner(['docker', 'inspect', '--format',
                '{{index .Config.Labels "org.brisance.preflight"}}', container_id], env=self.env, timeout=15)
            if owner.strip() != self.owner_label:
                return
            self.runner(['docker', 'stop', '--time', '5', container_id], env=self.env, timeout=15)
        except CheckFailure:
            self.warn('A diagnostic container may still exist: {}. No unrelated container was stopped.'.format(container_id))

    def step(self, label, action):
        started = time.monotonic()
        record = {'name': label, 'started_at_utc': utc()}
        self.report['checks'].append(record)
        try:
            with Progress(label):
                result = action()
            record['status'] = 'passed'
            if result is not None:
                record['details'] = result
            return result
        except BaseException as exc:
            record['status'] = 'cancelled' if isinstance(exc, (Cancelled, KeyboardInterrupt, EOFError)) else 'failed'
            record['error'] = str(exc)
            raise
        finally:
            record['duration_seconds'] = round(time.monotonic() - started, 3)

    def warn(self, message):
        if message not in self.report['warnings']:
            print('NOTE: ' + message, flush=True)
            self.report['warnings'].append(message)

    def check_host(self):
        host = host_capacity()
        if host['system'] != 'Linux' or host['machine'] not in ('x86_64', 'amd64'):
            raise CheckFailure('This image bundle is checked on Linux x86_64. Other platforms require a separately verified image bundle.')
        requested_cpu = max(stage['cpus'] for stage in self.config['resources'].values())
        requested_ram = max(stage['memory_gb'] for stage in self.config['resources'].values()) * configuration.GIB
        if host['logical_cpus_available'] <= requested_cpu:
            raise CheckFailure('CPU limits require {} logical CPUs plus capacity for Nextflow; {} are visible. Reduce limits or use a suitable server.'.format(
                requested_cpu, host['logical_cpus_available']))
        if host['memory_available_bytes'] < requested_ram:
            raise CheckFailure('Available host RAM is below the largest configured container memory limit. Reduce limits or free resources.')
        return host

    def check_storage(self):
        estimate = configuration.storage_estimate(self.config)
        if estimate['available_bytes'] < estimate['recommended_available_bytes']:
            self.warn('Available analysis-disk space is below the recommendation (8x, with a 32 GiB planning floor). Environment checks can run, but this is not approval to start analysis.')
        estimate['meets_recommendation'] = estimate['available_bytes'] >= estimate['recommended_available_bytes']
        self.report['storage'] = estimate
        return estimate

    def check_java(self):
        java_home = self.env.get('JAVA_HOME')
        selected = find_executable(self.java_path, [self.env.get('JAVA_CMD'),
            str(Path(java_home) / 'bin/java') if java_home else None, 'java'], 'Java')
        output = self.run_command([selected, '-version'])
        match = re.search(r'(?:openjdk|java) version "(\d+)(?:[.\-"+])', output)
        if not match or not 17 <= int(match.group(1)) <= 26:
            raise CheckFailure('Java 17–26 is required. Activate a compatible environment or pass --java /absolute/path/to/java. System Java was not changed.')
        self.env['JAVA_CMD'] = selected
        # Keep a stale JAVA_HOME from redirecting the explicitly selected JVM.
        self.env.pop('JAVA_HOME', None)
        return {'executable': selected, 'version_output': output}

    def check_nextflow(self):
        evaluated = Path(__file__).resolve().parent.parent / ('nextflow-' + NEXTFLOW_VERSION + '-dist')
        selected = find_executable(self.nextflow_path, [evaluated, 'nextflow'], 'Nextflow ' + NEXTFLOW_VERSION)
        output = self.run_command([selected, '-version'], timeout=90)
        if not re.search(r'\bversion\s+' + re.escape(NEXTFLOW_VERSION) + r'(?=\s|$)', output):
            raise CheckFailure('Use the evaluated Nextflow {} executable (select it with --nextflow). Other installations are not replaced.'.format(NEXTFLOW_VERSION))
        return {'executable': selected, 'version_output': output}

    def check_docker(self):
        explicit_host = self.env.get('DOCKER_HOST')
        explicit_context = self.env.get('DOCKER_CONTEXT')
        # DOCKER_CONTEXT takes precedence over DOCKER_HOST in the Docker CLI.
        if explicit_context:
            endpoint = self.run_command(['docker', 'context', 'inspect', explicit_context,
                                         '--format', '{{.Endpoints.docker.Host}}'])
        elif explicit_host:
            endpoint = explicit_host
        else:
            endpoint = self.run_command(['docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}'])
        if not endpoint.startswith('unix://'):
            raise CheckFailure('The selected Docker endpoint is remote. Choose a local Unix-socket context; no context was changed.')
        version = self.run_command(['docker', 'version', '--format', '{{.Server.Version}}'])
        if not re.match(r'\d+\.\d+', version) or tuple(map(int, version.split('.')[:2])) < (20, 10):
            raise CheckFailure('Docker server 20.10 or later is required. Ask the server administrator to resolve installation/access problems.')
        info = json.loads(self.run_command(['docker', 'info', '--format',
            '{"os":{{json .OSType}},"architecture":{{json .Architecture}},"root":{{json .DockerRootDir}}}']))
        if info['os'] != 'linux' or info['architecture'] not in ('x86_64', 'amd64'):
            raise CheckFailure('The local Docker daemon must run Linux x86_64 images.')
        self.warn('Image downloads use Docker storage at {}. Their extra size is not included in the FASTQ-based estimate.'.format(info['root']))
        return {'server_version': version, **info}

    def check_gpus(self):
        requested = sorted({device for stage in ('alignment', 'bqsr', 'calling')
                            for device in self.config['resources'][stage]['gpu_devices']})
        output = self.run_command(['nvidia-smi', '-i', ','.join(map(str, requested)),
            '--query-gpu=index,uuid,name,memory.total,memory.free,utilization.gpu,driver_version',
            '--format=csv,noheader,nounits'])
        found = {}
        for row in csv.reader(output.splitlines(), skipinitialspace=True):
            if len(row) != 7:
                raise CheckFailure('Unexpected nvidia-smi GPU output.')
            index, uuid, name, total, free, utilization, driver = (value.strip() for value in row)
            index, total, free, utilization = int(index), int(total), int(free), int(utilization)
            if index not in requested or index in found or not uuid.startswith('GPU-'):
                raise CheckFailure('Missing, duplicate or unsupported GPU identity; MIG devices are not accepted by this check.')
            if utilization or free < total * 0.90:
                raise CheckFailure('Selected GPU {} appears busy. Coordinate access or select another GPU; no job was stopped.'.format(index))
            if 'A100' not in name or total < 80000:
                self.warn('GPU {} ({}) differs from the HG008 A100 80 GB evaluation. These checks do not establish Parabricks support or sufficient GPU memory for this model.'.format(index, name))
            found[index] = {'index': index, 'uuid': uuid, 'name': name, 'total_mib': total,
                            'free_mib': free, 'utilization_percent': utilization, 'driver': driver}
        if set(found) != set(requested):
            raise CheckFailure('Not all selected GPUs were found.')
        selected_uuids = {gpu['uuid'] for gpu in found.values()}
        apps = self.run_command(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader,nounits'])
        for row in csv.reader(apps.splitlines(), skipinitialspace=True):
            if row and row[0].strip() in selected_uuids:
                raise CheckFailure('A compute process is present on a selected GPU. No process was stopped.')
        mig = self.run_command(['nvidia-smi', '-i', ','.join(map(str, requested)),
                               '--query-gpu=index,mig.mode.current', '--format=csv,noheader,nounits'])
        mig_seen = set()
        for row in csv.reader(mig.splitlines(), skipinitialspace=True):
            if len(row) != 2 or row[1].strip().lower() not in ('disabled', '[n/a]', 'n/a', '[not supported]', 'not supported'):
                raise CheckFailure('MIG is enabled or its state could not be established. This GPU configuration has not been checked.')
            index = int(row[0].strip())
            if index not in requested or index in mig_seen:
                raise CheckFailure('Unexpected GPU identity in the MIG state query.')
            mig_seen.add(index)
        if mig_seen != set(requested):
            raise CheckFailure('MIG state was not reported for every selected GPU.')
        self.gpus = [found[index] for index in requested]
        return self.gpus

    def inspect_image(self, image):
        try:
            output = self.run_command(['docker', 'image', 'inspect', image, '--format',
                '{"id":{{json .Id}},"digests":{{json .RepoDigests}},"os":{{json .Os}},"architecture":{{json .Architecture}}}'])
        except CheckFailure as exc:
            if 'no such image' in str(exc).lower() or 'no such object' in str(exc).lower():
                return None
            raise
        details = json.loads(output)
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', details['id']):
            raise CheckFailure('Unexpected Docker image identifier.')
        if details['os'] != 'linux' or details['architecture'] != 'amd64':
            raise CheckFailure('Required image is not Linux amd64: ' + image)
        return details

    def approved_pull(self, spec, reason):
        event = {'image': spec['image'], 'reason': reason, 'requested_at_utc': utc(), 'approved': False}
        self.report['downloads'].append(event)
        if not self.allow_downloads or not sys.stdin.isatty():
            raise CheckFailure('{}: {}. Download required image {} after authorization, or rerun interactively.'.format(spec['name'], reason, spec['image']))
        print('\n{}: {}.'.format(spec['name'], reason))
        print('This will not remove other versions or change running containers.')
        if not self.ask('Download the required image {}?'.format(spec['image']), default=False):
            raise Cancelled('Image download cancelled. No scientific analysis started.')
        event['approved'] = True
        try:
            self.downloader(spec['image'])
            event['status'] = 'completed'
        except BaseException:
            event['status'] = 'failed_or_interrupted'
            raise

    def container_command(self, image_id, command, gpu=False, mounts=None):
        self.container_counter += 1
        args = ['docker', 'run', '--rm', '--pull', 'never', '--network', 'none',
                '--label', 'org.brisance.preflight=' + self.owner_label,
                '--cidfile', str(self.directory / 'diagnostic-{}.cid'.format(self.container_counter)),
                '--user', '{}:{}'.format(os.getuid(), os.getgid()),
                '--cpus', '2', '--memory', '4g', '-e', 'JAVA_TOOL_OPTIONS=-Xmx512m']
        if gpu:
            args += ['--gpus', '"device={}"'.format(','.join(str(item['index']) for item in self.gpus))]
        for mount in mounts or []:
            args += ['--mount', mount]
        return args + [image_id] + command

    def image_version(self, spec, details):
        output = self.run_command(self.container_command(details['id'], spec['command'], spec.get('gpu', False)), timeout=90)
        if not all(re.search(pattern, output, re.M | re.I) for pattern in spec['patterns']):
            raise VersionMismatch(output)
        return output

    def required_image(self, spec):
        details = self.inspect_image(spec['image'])
        if details is None:
            raise ImageMissing('Required image not found: ' + spec['image'])
        return details

    def check_image(self, spec):
        try:
            details = self.step(spec['name'] + ' image', lambda: self.required_image(spec))
        except ImageMissing:
            self.approved_pull(spec, 'required image not found')
            details = self.step(spec['name'] + ' downloaded image', lambda: self.required_image(spec))
        self.report['images'][spec['image']] = dict(details)
        try:
            output = self.step(spec['name'] + ' tool version', lambda: self.image_version(spec, details))
        except VersionMismatch as exc:
            self.report['images'][spec['image']]['previous_version_output'] = exc.output
            self.approved_pull(spec, 'tool version does not match BRISANCE; refreshing this tag may change its image association')
            details = self.step(spec['name'] + ' refreshed image', lambda: self.required_image(spec))
            output = self.step(spec['name'] + ' refreshed tool version', lambda: self.image_version(spec, details))
        self.images[spec['image']] = details['id']
        self.report['images'][spec['image']].update(details)
        self.report['images'][spec['image']]['version_output'] = output
        print('Version verified: ' + spec['name'], flush=True)

    def check_gpu_container(self):
        image_id = self.images[IMAGES[1]['image']]
        output = self.run_command(self.container_command(image_id,
            ['nvidia-smi', '--query-gpu=uuid', '--format=csv,noheader'], gpu=True))
        visible = {line.strip() for line in output.splitlines() if line.strip()}
        expected = {item['uuid'] for item in self.gpus}
        if visible != expected:
            raise CheckFailure('Container GPU identities do not match the selected host GPUs.')
        return {'visible_gpu_uuids': sorted(visible), 'scope': 'NVIDIA runtime/driver visibility, not a CUDA kernel or scientific smoke test'}

    def check_mounts(self):
        files = [Path(row[field]) for row in self.config['samples'] for field in ('fastq_1', 'fastq_2')]
        fasta, reference_indices = configuration.reference_bundle(self.config['reference']['fasta'])
        files += [fasta, *reference_indices]
        for site in self.config['reference']['known_sites']:
            files += [Path(site), Path(site + '.tbi')]
        cache = self.config['reference']
        files += [Path(cache['vep_cache_dir']) / 'homo_sapiens' / ('113_' + cache['assembly']) / 'info.txt']
        image_id = self.images[IMAGES[2]['image']]
        for start in range(0, len(files), 32):
            chunk = files[start:start + 32]
            targets = ['/inputs/file{}'.format(i) for i in range(len(chunk))]
            mounts = ['type=bind,source={},target={},readonly'.format(path, target)
                      for path, target in zip(chunk, targets)]
            self.run_command(self.container_command(image_id,
                ['bash', '-euc', 'for file in "$@"; do test -f "$file" && test -r "$file"; done',
                 'check-input-access', *targets], mounts=mounts))
        self.run_command(self.container_command(image_id,
            ['bash', '-euc', 'test -w /out; : > /out/container-write-check.txt'],
            mounts=['type=bind,source={},target=/out'.format(self.directory)]))
        return {'read_only_input_mounts_checked': len(files), 'writable_probe': 'container-write-check.txt',
                'sequencing_contents_read': False}

    def run(self):
        self.step('Linux, CPU and available RAM', self.check_host)
        self.step('Analysis storage', self.check_storage)
        self.step('Java', self.check_java)
        self.step('Nextflow ' + NEXTFLOW_VERSION, self.check_nextflow)
        self.step('Local Docker daemon and user access', self.check_docker)
        self.step('Selected NVIDIA GPUs and driver access', self.check_gpus)
        for spec in IMAGES:
            self.check_image(spec)
        self.step('Selected GPU visibility inside the Parabricks container', self.check_gpu_container)
        self.step('Read-only input access and analysis-directory write access', self.check_mounts)
        # Downloads and other users may have changed disk/GPU state during checks.
        self.step('Current storage after image checks', self.check_storage)
        self.step('Current selected GPU availability', self.check_gpus)
        self.report['status'] = 'passed_with_notes' if self.report['warnings'] else 'passed'
        self.report['finished_at_utc'] = utc()
        print('\nENVIRONMENT CHECKS PASSED. No analysis started.')
        print('This is a dependency/access check, not a guarantee for every dataset or GPU model.')
        return self.report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('configuration', metavar='BRISANCE_JSON')
    parser.add_argument('--java', help='Installed compatible Java executable; does not change system Java.')
    parser.add_argument('--nextflow', help='Installed Nextflow 26.04.6 executable; does not replace other versions.')
    parser.add_argument('--no-download', action='store_true', help='Never offer or perform image downloads; fail if required images are missing or wrong.')
    args = parser.parse_args(argv)
    checker, directory, code = None, None, 1
    try:
        source = configuration.readable_file(str(Path(args.configuration).absolute()), ('.json',))
        with source.open() as handle:
            config = configuration.validate_configuration(json.load(handle))
        root = Path(config['analysis_dir'])
        if source != root / 'brisance.json' or not root.is_dir():
            raise CheckFailure('Use brisance.json in the analysis folder created by the settings-file runner.')
        reports = root / 'reports'
        if reports.is_symlink() or not reports.is_dir():
            raise CheckFailure('The analysis reports folder must exist and must not be a symlink.')
        directory = Path(tempfile.mkdtemp(prefix='environment-', dir=reports))
        checker = EnvironmentCheck(config, directory, java=args.java, nextflow=args.nextflow,
                                   allow_downloads=not args.no_download)
        # Fingerprint only the small configuration/program files, never FASTQs/BAMs.
        checker.report['configuration'] = {'path': str(source),
            'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        checker.report['interface_source_sha256'] = {
            name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('configure_brisance.py', 'check_environment.py')}
        checker.run()
        code = 0
    except (KeyboardInterrupt, EOFError, Cancelled) as exc:
        if checker:
            checker.report.update(status='cancelled', error=str(exc) or 'Interrupted by user.', finished_at_utc=utc())
        print('\nCANCELLED. No analysis started.', file=sys.stderr)
        code = 130
    except (CheckFailure, ValueError, OSError, TypeError, KeyError) as exc:
        if checker:
            checker.report.update(status='failed', error=str(exc), finished_at_utc=utc())
        print('\nERROR: ' + str(exc), file=sys.stderr)
        print('No analysis started. Input files and existing images were not deleted.', file=sys.stderr)
    finally:
        if checker and directory:
            try:
                with (directory / 'environment.json').open('x') as handle:
                    json.dump(checker.report, handle, indent=2)
                    handle.write('\n')
                print('Environment report: ' + str(directory / 'environment.json'))
            except OSError as exc:
                print('Could not save environment report: ' + str(exc), file=sys.stderr)
                code = 1
    return code


if __name__ == '__main__':
    sys.exit(main())
