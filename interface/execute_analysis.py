"""Confirmed, fresh execution of the configurable pipeline; no implicit resume."""

import csv
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

import configure_brisance as configuration
import check_environment as environment


IMAGE_KEYS = ('trim', 'parabricks', 'samtools', 'gatk', 'bcftools', 'vep')


def write_json(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')


def execution_parameters(config, images):
    fasta, indices = configuration.reference_bundle(config['reference']['fasta'])
    _, site_indices = configuration.known_sites_files(config['reference']['known_sites'],
        {path.name for path in [fasta, *indices]})
    if set(images) != set(IMAGE_KEYS) or any(not re.fullmatch(r'sha256:[0-9a-f]{64}', value) for value in images.values()):
        raise ValueError('Six checked immutable Docker image IDs are required.')
    return {'configuration': config, 'bundle': {'reference_indices': list(map(str, indices)),
            'known_indices': list(map(str, site_indices)),
            'cache_info': str(Path(config['reference']['vep_cache_dir']) / 'homo_sapiens' /
                              ('{}_{}'.format(config['reference']['vep_cache_version'], config['reference']['assembly'])) / 'info.txt')},
            'images': images}


def fresh_outputs(config):
    root = Path(config['analysis_dir'])
    for name in ('work', 'results'):
        directory = root / name
        if directory.is_symlink() or not directory.is_dir() or any(directory.iterdir()):
            raise ValueError('{} must be an empty real directory for a fresh analysis. Existing runs are never overwritten; choose a new analysis folder.'.format(name))


def publication_probe(config):
    """Check hard-link publication using only two new, owned, tiny probe names."""
    root = Path(config['analysis_dir'])
    work, results = root / 'work', root / 'results'
    if work.stat().st_dev != results.stat().st_dev:
        raise ValueError('Results and work must be on the same filesystem for space-efficient regular result files.')
    source = None
    target = None
    target_created = False
    try:
        with tempfile.NamedTemporaryFile(prefix='.brisance-probe-', dir=work, delete=False) as handle:
            source = Path(handle.name)
            handle.write(b'BRISANCE publication probe\n')
        target = results / source.name
        os.link(source, target)
        target_created = True
        if target.is_symlink() or not os.path.samefile(source, target):
            raise ValueError('Regular-file publication probe failed.')
        source.unlink()
        source = None
        if target.read_bytes() != b'BRISANCE publication probe\n':
            raise ValueError('Published probe did not survive removal of the work name.')
    finally:
        if source is not None:
            source.unlink(missing_ok=True)
        if target_created:
            target.unlink(missing_ok=True)


def check_environment(config, runtime, no_download):
    directory = Path(tempfile.mkdtemp(prefix='environment-', dir=Path(config['analysis_dir']) / 'reports'))
    checker = environment.EnvironmentCheck(config, directory, java=runtime['java'], nextflow=runtime['nextflow'],
        allow_downloads=runtime['allow_downloads'] and not no_download)
    checker.report['configuration'] = {'path': str(Path(config['analysis_dir']) / 'brisance.json'),
        'sha256': hashlib.sha256((Path(config['analysis_dir']) / 'brisance.json').read_bytes()).hexdigest()}
    checker.report['interface_source_sha256'] = {
        name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ('configure_brisance.py', 'check_environment.py', 'run_from_file.py', 'execute_analysis.py')}
    try:
        checker.run()
        checker.step('Regular result-file publication', lambda: publication_probe(config))
    except BaseException as exc:
        checker.report.update(status='failed', error=str(exc), finished_at_utc=environment.utc())
        raise
    finally:
        write_json(directory / 'environment.json', checker.report)
        print('Environment report: ' + str(directory / 'environment.json'), flush=True)
    return checker


def stream_command(command, directory, env):
    """Keep visible logs; interrupt only this launched Nextflow process group."""
    with (directory / 'console.log').open('x') as log:
        process = subprocess.Popen(command, cwd=directory, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace', start_new_session=True)
        try:
            for line in process.stdout:
                print(line, end='', flush=True)
                log.write(line)
                log.flush()
            return process.wait()
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=15)
            raise
        finally:
            process.stdout.close()


def completion_check(config, report_dir):
    with (report_dir / 'trace.tsv').open(newline='') as handle:
        tasks = list(csv.DictReader(handle, delimiter='\t'))
    if len(tasks) != len(config['samples']) + 13 or any(row['status'] != 'COMPLETED' or row['exit'] != '0' for row in tasks):
        raise ValueError('The trace does not contain all expected successful fresh tasks. Inspect the saved reports.')
    root = Path(config['analysis_dir']) / 'results'
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('An unexpected symbolic link was found among published results: ' + str(path))
    names = {row['role']: row['sample'] for row in config['samples']}
    pair = names['tumor'] + '_vs_' + names['normal']
    directory = root / 'stage8' / 'final' / pair
    vcf = directory / (pair + '.PASS_TLOD.vcf.gz')
    for path in (vcf, Path(str(vcf) + '.tbi')):
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Missing final regular VCF/index: ' + str(path))
    with (directory / 'tlod_counts.tsv').open(newline='') as handle:
        counts = {row['set']: int(row['variant_records']) for row in csv.DictReader(handle, delimiter='\t')}
    if set(counts) != {'annotated_PASS', 'PASS_TLOD'} or any(value < 0 for value in counts.values()):
        raise ValueError('Invalid final count report.')
    return {'tasks_completed': len(tasks), 'final_vcf': str(vcf), 'counts': counts,
            'scope': 'Execution/regular-file checks, not a biological accuracy benchmark.'}


def execute(config, runtime, settings_record, no_download=False):
    if not runtime['check_environment']:
        raise ValueError('--run requires [runtime] check_environment = true.')
    root = Path(config['analysis_dir'])
    # flock does not delete a stale PID file or interfere with another user/job.
    lock_path = root / '.brisance-run.lock'
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Another launcher is using this analysis folder.') from exc
        fresh_outputs(config)
        checker = check_environment(config, runtime, no_download)
        estimate = configuration.storage_estimate(config)
        if estimate['available_bytes'] < estimate['recommended_available_bytes']:
            raise ValueError('Free space is below the recommendation. No analysis started.')
        images = {key: checker.images[spec['image']] for key, spec in zip(IMAGE_KEYS, environment.IMAGES)}
        params = execution_parameters(config, images)
        directory = Path(tempfile.mkdtemp(prefix='execution-', dir=root / 'reports'))
        source = Path(__file__).resolve().parents[1] / 'pipeline'
        if not (source / 'main.nf').is_file():
            raise ValueError('The pipeline/ folder must be installed beside interface/. Transfer both folders.')
        shutil.copytree(source, directory / 'source' / 'pipeline', ignore=shutil.ignore_patterns('__pycache__'))
        source = directory / 'source' / 'pipeline'
        write_json(directory / 'source-sha256.json', {str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in sorted(source.rglob('*')) if path.is_file()})
        parameter_file = directory / 'nextflow-params.json'
        write_json(parameter_file, params)
        nf = next(record['details']['executable'] for record in checker.report['checks'] if record['name'] == 'Nextflow ' + environment.NEXTFLOW_VERSION)
        command = [nf, '-C', str(source / 'nextflow.config'), '-log', str(directory / 'nextflow.log'),
                   'run', str(source / 'main.nf'), '-params-file', str(parameter_file)]
        preflight = directory / 'workflow-validation'
        preflight.mkdir()
        print('Loading the configurable Nextflow workflow (metadata only)...', flush=True)
        validation_command = list(command)
        validation_command[validation_command.index('-log') + 1] = str(preflight / 'nextflow.log')
        code = stream_command(validation_command + ['--mode', 'validate', '-work-dir', str(preflight / 'work'), '-ansi-log', 'false'], preflight, checker.env)
        if code:
            return code
        print('\nWorkflow: trimming/FastQC -> alignment -> BQSR -> read groups -> somatic calling -> filtering -> VEP -> positive TLOD.')
        print('One task at a time; selected GPUs are not reserved. Results will be regular files in ' + str(root / 'results'))
        if not configuration.yes_no('Start this analysis now?', default=False):
            print('Cancelled before analysis. Settings and preflight reports were preserved.')
            return 0
        # Refresh observations after the final prompt. Never trust a stale GPU report.
        checker.step('Selected GPU availability immediately before analysis', checker.check_gpus)
        fresh_outputs(config)
        if configuration.storage_estimate(config)['available_bytes'] < estimate['recommended_available_bytes']:
            raise ValueError('Available space changed below the recommendation. No analysis started.')
        if configuration.validate_configuration(config) != config:
            raise ValueError('Input/resource settings changed during confirmation. No analysis started.')
        with (root / 'brisance.json').open() as handle:
            if json.load(handle) != config:
                raise ValueError('The saved configuration changed before execution. No analysis started.')
        command += ['--mode', 'run', '-work-dir', str(root / 'work'), '-with-trace', str(directory / 'trace.tsv'),
                    '-with-report', str(directory / 'report.html'), '-with-timeline', str(directory / 'timeline.html'), '-ansi-log', 'false']
        record = {'status': 'running', 'started_at_utc': environment.utc(), 'command': command,
                  'settings_record': str(settings_record), 'environment_report': str(checker.directory / 'environment.json'),
                  'image_ids': images, 'initial_storage': estimate, 'automatic_resume': False, 'automatic_cleanup': False,
                  'publication': 'Regular hard-linked files on one filesystem; no symbolic published results.'}
        write_json(directory / 'start.json', record)
        write_json(directory / 'launch-observations.json', checker.report)
        started = time.monotonic()
        try:
            print('Starting analysis. Reports: ' + str(directory), flush=True)
            code = stream_command(command, directory, checker.env)
            record['exit_code'] = code
            record['status'] = 'failed' if code else 'completed'
            if not code:
                record['completion'] = completion_check(config, directory)
                print('Final VCF: ' + record['completion']['final_vcf'])
                print('Final variant records: ' + str(record['completion']['counts']['PASS_TLOD']))
            return code
        except BaseException as exc:
            record.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed', error=str(exc))
            raise
        finally:
            record.update(finished_at_utc=environment.utc(), elapsed_seconds=round(time.monotonic() - started, 3))
            write_json(directory / 'completion.json', record)
            print('Reports preserved: ' + str(directory), flush=True)
