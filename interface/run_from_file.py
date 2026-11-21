#!/usr/bin/env python3
"""Read fixed BRISANCE settings; check dependencies, or explicitly request a fresh run."""

import argparse
import configparser
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import configure_brisance as configuration


RESOURCE_SECTIONS = {
    'trim_resources': ('trim', {'cpu_limit': 'cpus', 'memory_gb': 'memory_gb', 'fastqc_heap_gb': 'fastqc_heap_gb'}),
    'alignment': ('alignment', {'cpu_limit': 'cpus', 'memory_gb': 'memory_gb',
                               'bwa_thread_pool': 'bwa_thread_pool', 'sorting_memory_gb': 'sorting_memory_gb'}),
    'bqsr': ('bqsr', {'cpu_limit': 'cpus', 'memory_gb': 'memory_gb', 'threads': 'threads'}),
    'read_groups': ('read_groups', {'cpu_limit': 'cpus', 'memory_gb': 'memory_gb', 'index_threads': 'index_threads'}),
    'calling': ('calling', {'cpu_limit': 'cpus', 'memory_gb': 'memory_gb', 'threads': 'threads'}),
    'filtering': ('filtering', {'cpu_limit': 'cpus', 'memory_gb': 'memory_gb', 'java_heap_gb': 'java_heap_gb'}),
    'annotation': ('annotation', {'cpu_limit': 'cpus', 'memory_gb': 'memory_gb', 'forks': 'forks'}),
    'utilities': ('utilities', {'cpu_limit': 'cpus', 'memory_gb': 'memory_gb'}),
}
FIELDS = {
    'analysis': {'folder', 'input_mode'},
    'tumor': {'sample', 'r1', 'r2', 'bam', 'bam_index'},
    'normal': {'sample', 'r1', 'r2', 'bam', 'bam_index'},
    'somatic': {'pon', 'pon_prepared'},
    'qc': {'enabled'},
    'orientation': {'mode', 'priors'},
    'contamination': {'mode', 'sites', 'table', 'segments'},
    'reference': {'fasta', 'assembly', 'known_sites', 'vep_cache', 'vep_cache_version'},
    'trimming': {'adapters', 'adapter_r1', 'adapter_r2', 'quality', 'min_read_length'},
    'runtime': {'java', 'nextflow', 'check_environment', 'allow_downloads'},
}
for section, (_, mapping) in RESOURCE_SECTIONS.items():
    FIELDS[section] = set(mapping)
FIELDS['alignment'].add('gpus')
FIELDS['calling'].add('gpus')
FIELDS['bqsr'].add('gpu')


def plain(value):
    value = value.strip()
    if '\n' not in value and len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
        return value[1:-1].strip()
    return value


def parse_settings(path, content=None):
    """Parse data only. Do not source/evaluate the file or access sequencing files."""
    parser = configparser.ConfigParser(interpolation=None, strict=True,
        inline_comment_prefixes=('#', ';'), empty_lines_in_values=False)
    if content is None:
        with Path(path).open() as handle:
            parser.read_file(handle)
    else:
        parser.read_string(content, source=str(path))
    if parser.defaults():
        raise ValueError('Use named configuration sections rather than [DEFAULT].')
    sections = {}
    for original in parser.sections():
        name = original.lower()
        if name not in FIELDS:
            raise ValueError('Unknown section [{}].'.format(original))
        if name in sections:
            raise ValueError('Repeated section [{}].'.format(original))
        sections[name] = parser[original]
        unknown = set(parser[original]) - FIELDS[name]
        if unknown:
            raise ValueError('Unknown setting in [{}]: {}.'.format(original, ', '.join(sorted(unknown))))

    def get(section, key, default=None):
        raw = sections.get(section, {}).get(key)
        if raw is None:
            if default is not None:
                return default
            raise ValueError('Missing [{}] {}.'.format(section, key))
        return plain(raw)

    def integer(section, key, default=None, minimum=1):
        try:
            return configuration.positive_int(get(section, key, default), minimum=minimum)
        except ValueError as exc:
            raise ValueError('[{}] {}: {}'.format(section, key, exc)) from exc

    def boolean(key, default, section='runtime'):
        value = str(get(section, key, str(default))).lower()
        if value not in configparser.ConfigParser.BOOLEAN_STATES:
            raise ValueError('[{}] {} must be true or false.'.format(section, key))
        return configparser.ConfigParser.BOOLEAN_STATES[value]

    def paths(section, key):
        value = get(section, key)
        result = [plain(line) for line in value.splitlines() if line.strip()]
        if not result:
            raise ValueError('[{}] {} needs at least one path, one file per line.'.format(section, key))
        return result

    def gpu_list(section):
        return configuration.devices(','.join(part.strip() for part in get(section, 'gpus').split(',')))

    input_mode = get('analysis', 'input_mode', 'fastq').lower()
    if input_mode not in ('fastq', 'bam'):
        raise ValueError('[analysis] input_mode must be fastq or bam.')
    rows = []
    for role in ('tumor', 'normal'):
        sample = configuration.identifier(get(role, 'sample'))
        forbidden = {'r1', 'r2'} if input_mode == 'bam' else {'bam', 'bam_index'}
        if forbidden & set(sections.get(role, {})):
            raise ValueError('Do not mix BAM and FASTQ settings in [{}].'.format(role))
        if input_mode == 'bam':
            bam = get(role, 'bam')
            rows.append({'sample': sample, 'role': role, 'bam': bam,
                         'bam_index': get(role, 'bam_index', bam + '.bai')})
            continue
        r1, r2 = paths(role, 'r1'), paths(role, 'r2')
        if len(r1) != len(r2):
            raise ValueError('[{}] R1/R2 counts differ ({} versus {}). Put matching mates in the same list order.'.format(role, len(r1), len(r2)))
        for number, (first, second) in enumerate(zip(r1, r2), start=1):
            rows.append({'sample': sample, 'role': role, 'pair_id': '{}_pair{}'.format(sample, number),
                         'fastq_1': first, 'fastq_2': second})
    resources = {stage: dict(values) for stage, values in configuration.DEFAULT_RESOURCES.items()}
    for section, (stage, mapping) in RESOURCE_SECTIONS.items():
        for external, internal in mapping.items():
            resources[stage][internal] = integer(section, external, resources[stage][internal])
    resources['alignment']['gpu_devices'] = gpu_list('alignment') if input_mode == 'fastq' else [0]
    resources['bqsr']['gpu_devices'] = [integer('bqsr', 'gpu', resources['alignment']['gpu_devices'][0], minimum=0)]
    resources['calling']['gpu_devices'] = gpu_list('calling')
    adapter_mode = get('trimming', 'adapters', 'auto').lower()
    if adapter_mode == 'automatic':
        adapter_mode = 'auto'
    adapter_r1, adapter_r2 = get('trimming', 'adapter_r1', ''), get('trimming', 'adapter_r2', '')
    if adapter_mode == 'custom' and (not adapter_r1 or not adapter_r2):
        raise ValueError('Custom adapters require both [trimming] adapter_r1 and adapter_r2.')
    config = {
        'schema_version': configuration.SCHEMA_VERSION,
        'analysis_dir': get('analysis', 'folder'), 'samples': rows,
        'reference': {'fasta': get('reference', 'fasta'), 'assembly': get('reference', 'assembly', 'GRCh38'),
                      'known_sites': paths('reference', 'known_sites') if input_mode == 'fastq' else [], 'vep_cache_dir': get('reference', 'vep_cache'),
                      'vep_cache_version': integer('reference', 'vep_cache_version', 113)},
        'trimming': {'adapter_mode': adapter_mode, 'adapter_r1': adapter_r1 or None, 'adapter_r2': adapter_r2 or None,
                     'quality': integer('trimming', 'quality', 20, minimum=0),
                     'min_read_length': integer('trimming', 'min_read_length', 20)},
        'resources': resources,
    }
    # Preserve the exact legacy JSON when optional features are not requested.
    if input_mode == 'bam':
        config['input_mode'] = 'bam'
    pon = get('somatic', 'pon', '')
    prepared = boolean('pon_prepared', False, 'somatic')
    if prepared and not pon:
        raise ValueError('pon_prepared requires [somatic] pon.')
    if pon:
        config['somatic'] = {'pon': pon, 'pon_prepared': prepared}
    if boolean('enabled', False, 'qc'):
        config['qc'] = {'enabled': True}
    for section, inputs in (('orientation', ('priors',)), ('contamination', ('sites', 'table', 'segments'))):
        mode = get(section, 'mode', 'off').lower()
        supplied = {key: get(section, key, '') for key in inputs if get(section, key, '')}
        if mode not in ('off', 'auto', 'provided'):
            raise ValueError('[{}] mode must be off, auto or provided.'.format(section))
        if mode == 'off':
            if supplied:
                raise ValueError('[{}] inputs require an active mode; remove stale inputs when off.'.format(section))
        else:
            config[section] = {'mode': mode, **supplied}
    runtime = {'java': get('runtime', 'java', '') or None, 'nextflow': get('runtime', 'nextflow', '') or None,
               'check_environment': boolean('check_environment', True), 'allow_downloads': boolean('allow_downloads', True)}
    return config, runtime


def existing_configuration(config):
    root = Path(config['analysis_dir'])
    if not root.exists() and not root.is_symlink():
        configuration.new_destination(str(root))
        return False
    if root.is_symlink() or not root.is_dir():
        raise ValueError('The analysis destination must not be a symlink or non-directory.')
    stored = root / 'brisance.json'
    if stored.is_symlink() or not stored.is_file():
        raise ValueError('The analysis folder already exists without a saved BRISANCE configuration. Choose a new folder.')
    with stored.open() as handle:
        previous = json.load(handle)
    if previous != config:
        raise ValueError('This analysis folder contains different settings. Choose a new analysis folder to preserve the earlier configuration.')
    for name in ('results', 'reports', 'work'):
        directory = root / name
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError('Existing {} folder must be a real directory.'.format(name))
    sheet = root / 'samplesheet.csv'
    if sheet.is_symlink() or not sheet.is_file():
        raise ValueError('The saved samplesheet is missing or is a symlink.')
    with sheet.open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    if rows != config['samples']:
        raise ValueError('Saved samplesheet differs from the configuration. Nothing will be overwritten.')
    return True


def archive_settings(source, config, estimate, summary, payload):
    directory = Path(tempfile.mkdtemp(prefix='settings-', dir=Path(config['analysis_dir']) / 'reports'))
    with (directory / 'settings.ini').open('xb') as handle:
        handle.write(payload)
    with (directory / 'summary.txt').open('x') as handle:
        handle.write(summary + '\n')
    with (directory / 'storage-estimate.json').open('x') as handle:
        json.dump(estimate, handle, indent=2)
        handle.write('\n')
    with (directory / 'source.json').open('x') as handle:
        json.dump({'settings_path': str(Path(source).resolve()), 'settings_sha256': hashlib.sha256(payload).hexdigest(),
                   'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, handle, indent=2)
        handle.write('\n')
    return directory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('settings', metavar='SETTINGS_INI', help='Editable settings file; not a questionnaire.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='Read settings, check metadata and show the summary; no questions, writes or external commands.')
    mode.add_argument('--prepare-only', action='store_true', help='Ask for storage/configuration confirmation and save files, without running environment checks.')
    mode.add_argument('--run', action='store_true', help='Check the environment and configurable workflow, then ask separately before starting a fresh analysis.')
    parser.add_argument('--no-download', action='store_true', help='Refuse missing/wrong images rather than offering downloads.')
    parser.add_argument('--yes', action='store_true', help='With --run only: explicitly authorize unattended execution; disables image downloads and records this choice.')
    args = parser.parse_args(argv)
    if args.yes and not args.run:
        parser.error('--yes requires --run.')
    try:
        source = Path(args.settings).expanduser().resolve(strict=True)
        if not source.is_file() or source.stat().st_size > 1024 * 1024:
            raise ValueError('Use a regular settings file no larger than 1 MiB.')
        payload = source.read_bytes()
        raw, runtime = parse_settings(source, content=payload.decode('utf-8'))
        if args.yes:
            runtime['allow_downloads'] = False
        if Path(raw['analysis_dir']).is_symlink():
            raise ValueError('Choose a real analysis folder, not a symlink.')
        config = configuration.validate_configuration(raw)
        if args.run and not runtime['check_environment']:
            raise ValueError('--run requires [runtime] check_environment = true.')
        reuse = existing_configuration(config)
        estimate = configuration.storage_estimate(config)
        summary = configuration.execution_summary(config, estimate)
        print('Settings file: ' + str(source) + '\n')
        print(summary + '\n')
        if reuse:
            print('Existing saved settings match. Results will not be overwritten or resumed.\n')
        if args.check:
            print('SETTINGS CHECK OK. Nothing written; no external commands or analysis started.')
            return 0
        if not args.yes and not sys.stdin.isatty():
            raise ValueError('Confirmation needs an interactive terminal. Use --check for a read-only settings check.')
        if estimate['available_bytes'] < estimate['recommended_available_bytes']:
            print('WARNING: free space is below the recommendation; this operation can prepare/check settings only, not approve an analysis.')
        if not args.yes and not configuration.yes_no('Continue with these settings and the storage recommendation?', default=False):
            print('Cancelled. No configuration, downloads or analysis started.')
            return 0
        if source.read_bytes() != payload:
            raise ValueError('The settings file changed after the summary. Rerun to review the updated values before confirming.')
        if not reuse:
            configuration.save_configuration(config, estimate, summary)
        report = archive_settings(source, config, estimate, summary, payload)
        if args.yes:
            (report / 'unattended-authorization.txt').write_text('Explicit --run --yes supplied; downloads disabled.\n')
        print('Settings record: ' + str(report))
        if args.run:
            import execute_analysis
            return execute_analysis.execute(config, runtime, report, no_download=args.no_download, approved=args.yes)
        if args.prepare_only or not runtime['check_environment']:
            print('Configuration saved. Environment checks not requested; no analysis started.')
            return 0
        command = [sys.executable, '-B', str(Path(__file__).with_name('check_environment.py')),
                   str(Path(config['analysis_dir']) / 'brisance.json')]
        for flag, value in [('--java', runtime['java']), ('--nextflow', runtime['nextflow'])]:
            if value:
                command += [flag, value]
        if args.no_download or not runtime['allow_downloads']:
            command.append('--no-download')
        print('Starting dependency/access checks only. No scientific analysis will be started.', flush=True)
        return subprocess.run(command, check=False).returncode
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled/interrupted. Any created files and reports were preserved.', file=sys.stderr)
        return 130
    except RuntimeError as exc:
        print('\nERROR: ' + str(exc), file=sys.stderr)
        return 1
    except (ValueError, OSError, configparser.Error, TypeError, KeyError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        print(('Inspect the preserved execution reports. ' if args.run else 'No scientific analysis started. ') +
              'Existing inputs and results were not deleted.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
