#!/usr/bin/env python3
"""Configure BRISANCE; optionally check its environment. Never start an analysis."""

import argparse
import csv
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


SCHEMA_VERSION = 1
SAFE_PATH = re.compile(r"/[A-Za-z0-9_./-]+\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
GIB = 1024 ** 3
TIB = 1024 ** 4
DEFAULT_RESOURCES = {
    'trim': {'cpus': 2, 'memory_gb': 100, 'fastqc_heap_gb': 8},
    'alignment': {'cpus': 64, 'memory_gb': 256, 'bwa_thread_pool': 16,
                  'sorting_memory_gb': 128},
    'bqsr': {'cpus': 24, 'memory_gb': 128, 'threads': 16},
    'read_groups': {'cpus': 10, 'memory_gb': 8, 'index_threads': 8},
    'calling': {'cpus': 64, 'memory_gb': 256, 'threads': 24},
    'filtering': {'cpus': 4, 'memory_gb': 16, 'java_heap_gb': 8},
    'annotation': {'cpus': 10, 'memory_gb': 32, 'forks': 8},
    'utilities': {'cpus': 2, 'memory_gb': 4},
}
SHEET_COLUMNS = ['sample', 'role', 'pair_id', 'fastq_1', 'fastq_2']


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError('Use an identifier starting with a letter/number, followed by letters, numbers, dots, underscores or hyphens.')
    return value


def absolute_path(value):
    if not isinstance(value, str) or not SAFE_PATH.fullmatch(value):
        raise ValueError('Use an absolute Linux path without spaces, quotes or shell characters.')
    path = Path(value).resolve(strict=False)
    if not SAFE_PATH.fullmatch(str(path)):
        raise ValueError('The resolved path must also contain no spaces, quotes or shell characters.')
    return path


def readable_file(value, suffixes=None):
    path = absolute_path(value)
    if not path.is_file() or not os.access(path, os.R_OK) or path.stat().st_size == 0:
        raise ValueError('Missing, unreadable or empty file: {}'.format(path))
    if not IDENTIFIER.fullmatch(path.name):
        raise ValueError('Unsupported file name: {}'.format(path.name))
    if suffixes and not path.name.endswith(tuple(suffixes)):
        raise ValueError('Expected {}: {}'.format(', '.join(suffixes), path))
    return path


def positive_int(value, minimum=1, maximum=None):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
        raise ValueError('Enter a whole number.')
    number = int(value)
    if number < minimum or (maximum is not None and number > maximum):
        raise ValueError('Value outside the allowed range (minimum {}).'.format(minimum))
    return number


def devices(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+(,[0-9]+)*', value):
        raise ValueError('Enter comma-separated GPU indices, for example 7,6,5 (no spaces).')
    result = [int(item) for item in value.split(',')]
    if len(set(result)) != len(result):
        raise ValueError('GPU indices must be distinct.')
    return result


def adapter_sequence(value):
    if not isinstance(value, str):
        raise ValueError('Enter an adapter DNA sequence.')
    value = value.upper()
    if not re.fullmatch(r'[ACGTN]+', value):
        raise ValueError('Enter an adapter DNA sequence using A, C, G, T or N.')
    return value


def assembly_name(value):
    if value not in ('GRCh38', 'GRCh37'):
        raise ValueError('Select GRCh38 or GRCh37.')
    return value


def validate_samples(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError('Provide paired FASTQs for one tumor and one normal sample.')
    normalized, seen_files, seen_pairs, basenames_by_sample = [], set(), set(), {}
    trimmed_names_by_sample = {}
    names = {'tumor': set(), 'normal': set()}
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(SHEET_COLUMNS):
            raise ValueError('Sample entries require: ' + ','.join(SHEET_COLUMNS))
        sample, pair_id = identifier(row['sample']), identifier(row['pair_id'])
        role = row['role']
        if role not in names:
            raise ValueError('Sample role must be tumor or normal.')
        if pair_id in seen_pairs:
            raise ValueError('Duplicate pair identifier: ' + pair_id)
        seen_pairs.add(pair_id)
        names[role].add(sample)
        item = {'sample': sample, 'role': role, 'pair_id': pair_id}
        for field in ('fastq_1', 'fastq_2'):
            path = readable_file(row[field], ('.fastq.gz', '.fq.gz'))
            stat = path.stat()
            identity = (stat.st_dev, stat.st_ino)
            if identity in seen_files:
                raise ValueError('A FASTQ is used more than once: ' + str(path))
            seen_files.add(identity)
            # fq2bam stages all lanes for one sample into a common task folder.
            used_names = basenames_by_sample.setdefault(sample, set())
            if path.name in used_names:
                raise ValueError('FASTQs for the same sample need distinct file names: ' + path.name)
            used_names.add(path.name)
            # .fastq.gz and .fq.gz both lose their suffix during trimming.
            trimmed_name = re.sub(r'\.(fastq|fq)\.gz$', '', path.name) + ('_val_1.fq.gz' if field == 'fastq_1' else '_val_2.fq.gz')
            trimmed_names = trimmed_names_by_sample.setdefault(sample, set())
            if trimmed_name in trimmed_names:
                raise ValueError('FASTQ names would collide after trimming: ' + trimmed_name)
            trimmed_names.add(trimmed_name)
            item[field] = str(path)
        normalized.append(item)
    if any(len(values) != 1 for values in names.values()):
        raise ValueError('Provide exactly one tumor sample and one matched normal sample; multiple FASTQ pairs per sample are allowed.')
    if names['tumor'] == names['normal']:
        raise ValueError('Tumor and normal sample names must be different.')
    return normalized


def reference_bundle(value):
    fasta = readable_file(value, ('.fa', '.fasta', '.fna'))
    indices = [readable_file(str(fasta) + suffix) for suffix in
               ('.fai', '.amb', '.ann', '.bwt', '.pac', '.sa')]
    dictionary = fasta.with_suffix('.dict')
    if not dictionary.is_file():
        dictionary = Path(str(fasta) + '.dict')
    indices.append(readable_file(str(dictionary)))
    return fasta, indices


def known_sites_files(values, reference_names):
    if not isinstance(values, list) or not values:
        raise ValueError('Provide at least one known-sites VCF for this BQSR workflow.')
    files, indices, seen = [], [], set()
    for value in values:
        path = readable_file(value, ('.vcf.gz',))
        stat = path.stat()
        key = (stat.st_dev, stat.st_ino)
        if key in seen:
            raise ValueError('Duplicate known-sites VCF: ' + str(path))
        seen.add(key)
        index = readable_file(str(path) + '.tbi')
        for resource in (path, index):
            if resource.name in reference_names:
                raise ValueError('Resource file names collide in the task directory: ' + resource.name)
            reference_names.add(resource.name)
        files.append(str(path))
        indices.append(str(index))
    return files, indices


def cache_directory(value, assembly, version):
    cache = absolute_path(value)
    info = readable_file(str(cache / 'homo_sapiens' / '{}_{}'.format(version, assembly) / 'info.txt'))
    # Read metadata only. Do not traverse/copy the large shared cache.
    if info.stat().st_size > 1024 * 1024:
        raise ValueError('Unexpectedly large VEP cache info.txt.')
    fields = {}
    for line in info.read_text().splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            fields[parts[0]] = parts[1].strip()
    if fields.get('species') != 'homo_sapiens' or fields.get('assembly') != assembly:
        raise ValueError('VEP cache metadata must match homo_sapiens and ' + assembly)
    return cache


def validate_resources(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_RESOURCES):
        raise ValueError('Missing or unknown resource configuration section.')
    result = {}
    for stage, defaults in DEFAULT_RESOURCES.items():
        settings = value[stage]
        gpu_fields = {'gpu_devices'} if stage in ('alignment', 'bqsr', 'calling') else set()
        if not isinstance(settings, dict) or set(settings) != set(defaults) | gpu_fields:
            raise ValueError('Missing or unknown {} resource setting.'.format(stage))
        result[stage] = {key: positive_int(settings[key]) for key in defaults}
        if gpu_fields:
            gpu_list = settings['gpu_devices']
            if not isinstance(gpu_list, list) or not gpu_list:
                raise ValueError('Provide GPU indices for ' + stage)
            normalized = devices(','.join(str(item) for item in gpu_list))
            if stage == 'bqsr' and len(normalized) != 1:
                raise ValueError('ApplyBQSR currently uses one selected GPU.')
            result[stage]['gpu_devices'] = normalized
    for stage, field in [('trim', 'fastqc_heap_gb'), ('alignment', 'sorting_memory_gb'),
                         ('filtering', 'java_heap_gb')]:
        if result[stage][field] >= result[stage]['memory_gb']:
            raise ValueError('{} must be below the {} container memory limit.'.format(field, stage))
    if result['read_groups']['index_threads'] >= result['read_groups']['cpus']:
        raise ValueError('Read-group indexing needs a CPU limit greater than its additional indexing-thread parameter.')
    return result


def validate_configuration(config):
    required = {'schema_version', 'analysis_dir', 'samples', 'reference', 'trimming', 'resources'}
    if (not isinstance(config, dict) or set(config) != required or
            type(config['schema_version']) is not int or config['schema_version'] != SCHEMA_VERSION):
        raise ValueError('Unsupported configuration schema or unknown configuration fields.')
    root = absolute_path(config['analysis_dir'])
    if not IDENTIFIER.fullmatch(root.name):
        raise ValueError('Choose a named analysis folder, for example /data/analysis_01.')
    rows = validate_samples(config['samples'])
    ref = config['reference']
    if not isinstance(ref, dict) or set(ref) != {'fasta', 'known_sites', 'assembly', 'vep_cache_dir', 'vep_cache_version'}:
        raise ValueError('Missing or unknown reference setting.')
    if ref['assembly'] not in ('GRCh38', 'GRCh37'):
        raise ValueError('Select GRCh38 or GRCh37. Other assemblies are not covered by this configuration interface.')
    if type(ref['vep_cache_version']) is not int or ref['vep_cache_version'] != 113:
        raise ValueError('This software configuration uses VEP/cache version 113.')
    fasta, indices = reference_bundle(ref['fasta'])
    reference_names = {path.name for path in [fasta, *indices]}
    sites, _ = known_sites_files(ref['known_sites'], reference_names)
    cache = cache_directory(ref['vep_cache_dir'], ref['assembly'], ref['vep_cache_version'])
    trim = config['trimming']
    if not isinstance(trim, dict) or set(trim) != {'adapter_mode', 'adapter_r1', 'adapter_r2', 'quality', 'min_read_length'}:
        raise ValueError('Missing or unknown trimming setting.')
    if trim['adapter_mode'] not in ('auto', 'custom'):
        raise ValueError('Adapter mode must be auto or custom.')
    if trim['adapter_mode'] == 'auto':
        if trim['adapter_r1'] is not None or trim['adapter_r2'] is not None:
            raise ValueError('Automatic adapter detection cannot contain explicit adapters.')
        adapters = {'adapter_r1': None, 'adapter_r2': None}
    else:
        adapters = {key: adapter_sequence(trim[key]) for key in ('adapter_r1', 'adapter_r2')}
    resources = validate_resources(config['resources'])
    return {
        'schema_version': SCHEMA_VERSION, 'analysis_dir': str(root), 'samples': rows,
        'reference': {'fasta': str(fasta), 'known_sites': sites, 'assembly': ref['assembly'],
                      'vep_cache_dir': str(cache), 'vep_cache_version': 113},
        'trimming': {'adapter_mode': trim['adapter_mode'], **adapters,
                     'quality': positive_int(trim['quality'], minimum=0, maximum=93),
                     'min_read_length': positive_int(trim['min_read_length'])},
        'resources': resources,
    }


def nearest_existing_directory(path):
    current = path
    while not current.exists():
        current = current.parent
    if not current.is_dir():
        raise ValueError('The destination has a parent that is not a directory: ' + str(current))
    return current


def storage_estimate(config):
    input_bytes = sum(Path(row[key]).stat().st_size for row in config['samples']
                      for key in ('fastq_1', 'fastq_2'))
    root = Path(config['analysis_dir'])
    filesystem = nearest_existing_directory(root)
    return {
        'input_bytes': input_bytes,
        'estimated_additional_bytes': input_bytes * 5,
        'recommended_available_bytes': max(input_bytes * 8, 32 * GIB),
        'available_bytes': shutil.disk_usage(filesystem).free,
        'checked_directory': str(filesystem),
        'estimate_factor': 5, 'recommendation_factor': 8,
        'minimum_planning_allowance_bytes': 32 * GIB,
        'basis': 'Approximate retained work size after HG008 GRCh38 WGS execution, not a measured temporary disk peak.',
        'scope': 'One tumor-normal WGS pair; retained intermediates; no extra copy of inputs or BAMs. Existing references, VEP cache and Docker images excluded.',
    }


def human_bytes(value):
    if value >= TIB:
        return '{:.2f} TiB ({:.2f} TB)'.format(value / TIB, value / 10 ** 12)
    return '{:.2f} GiB ({:.2f} GB)'.format(value / GIB, value / 10 ** 9)


def execution_summary(config, estimate):
    root, res, ref, trim = Path(config['analysis_dir']), config['resources'], config['reference'], config['trimming']
    lines = ['BRISANCE — configuration summary', '',
             'Analysis: matched tumor-normal WGS', 'Sequencing: paired-end', '']
    for role in ('tumor', 'normal'):
        rows = [row for row in config['samples'] if row['role'] == role]
        lines += [role.capitalize() + ': ' + rows[0]['sample']]
        for row in rows:
            lines += ['  Pair: ' + row['pair_id'], '    R1: ' + row['fastq_1'], '    R2: ' + row['fastq_2']]
    lines += ['', 'Reference FASTA: ' + ref['fasta'], 'Assembly: ' + ref['assembly'], 'Known-sites VCFs:']
    lines += ['  ' + path + ' (corresponding .tbi found)' for path in ref['known_sites']]
    lines += ['VEP annotation cache: ' + ref['vep_cache_dir'], 'VEP/cache version: 113', '', 'Trimming:',
              '  Adapters: ' + ('automatic detection' if trim['adapter_mode'] == 'auto' else 'custom'),
              '  Quality cutoff: ' + str(trim['quality']),
              '  Minimum read length: {} bp'.format(trim['min_read_length'])]
    if trim['adapter_mode'] == 'custom':
        lines += ['  R1 adapter: ' + trim['adapter_r1'], '  R2 adapter: ' + trim['adapter_r2']]
    for stage, settings in res.items():
        lines += ['', stage.replace('_', ' ').capitalize() + ':']
        for key, value in settings.items():
            label = key.replace('_', ' ')
            if key == 'gpu_devices':
                value = ','.join(map(str, value))
            lines.append('  {}: {}'.format(label, value))
    lines += ['', 'Analysis folder: ' + str(root),
              '  Results: ' + str(root / 'results'), '  Reports and logs: ' + str(root / 'reports'),
              '  Managed work/intermediates/temporary files: ' + str(root / 'work'),
              'Configuration: ' + str(root / 'brisance.json'), '', 'Storage:',
              '  Input FASTQs already present: ' + human_bytes(estimate['input_bytes']),
              '  Estimated additional storage (5x): ' + human_bytes(estimate['estimated_additional_bytes']),
              '  Recommended free space (8x; at least 32 GiB planning allowance): ' + human_bytes(estimate['recommended_available_bytes']),
              '  Available on the destination filesystem: ' + human_bytes(estimate['available_bytes']),
              '  Existing references/cache/images are not counted again.',
              '  Estimate based on HG008/GRCh38; compression, data and configuration can change storage needs.',
              '  The 32 GiB floor is a planning policy for small inputs, not a measured minimum.',
              '  Quotas, other users and temporary disk peaks are not accounted for or reserved.']
    if estimate['available_bytes'] < estimate['recommended_available_bytes']:
        lines += ['WARNING: available space is below the recommendation. Configuration may be saved, but this is not approval to start processing.']
    if ref['assembly'] != 'GRCh38':
        lines += ['NOTE: the HG008 evaluation used GRCh38. GRCh37/hg19 execution has not been evaluated; matching contig names/sequences/resources remain required.']
    lines += ['', 'Checks: file existence, names, sizes, reference-index presence and VEP cache metadata.',
              'FASTQ contents, reference/index integrity, known-sites build compatibility and GPU/container availability have not been checked.',
              'This configuration step does not process sequencing data. Environment checks, if requested, are a separate step.']
    return '\n'.join(lines)


def prompt(text, validator=str, default=None, input_fn=None, output_fn=print):
    input_fn = input if input_fn is None else input_fn
    while True:
        value = input_fn(text + (' [{}]'.format(default) if default is not None else '') + ': ').strip()
        if not value and default is not None:
            value = str(default)
        try:
            return validator(value)
        except (ValueError, OSError) as exc:
            output_fn('Please check: ' + str(exc))


def yes_no(text, default=False, input_fn=None):
    input_fn = input if input_fn is None else input_fn
    while True:
        answer = input_fn(text + (' [Y/n]: ' if default else ' [y/N]: ')).strip().lower()
        if not answer:
            return default
        if answer in ('y', 'yes'):
            return True
        if answer in ('n', 'no'):
            return False
        print('Enter yes or no.')


def new_destination(value):
    path = absolute_path(value)
    identifier(path.name)
    if Path(value).is_symlink() or path.exists():
        raise ValueError('Choose a new analysis folder. Existing folders will not be overwritten.')
    parent = path.parent
    if not parent.is_dir() or not os.access(parent, os.W_OK | os.X_OK):
        raise ValueError('The parent folder must already exist and be writable: ' + str(parent))
    return str(path)


def collect_configuration():
    print('BRISANCE — analysis configuration\n')
    print('This step saves settings only. It does not start processing or modify input files.')
    print('Scope: one paired-end tumor-normal WGS analysis. Paths must be absolute and contain no spaces.\n')
    root = prompt('Where should BRISANCE save this analysis? (new folder)', new_destination)
    rows, used_samples, used_pairs, used_fastqs, used_names = [], set(), set(), set(), {}
    for role in ('tumor', 'normal'):
        print('\n' + role.capitalize() + ' sample')

        def unique_sample(value):
            value = identifier(value)
            if value in used_samples:
                raise ValueError('Tumor and normal sample names must be different.')
            return value

        sample = prompt('Sample name', unique_sample)
        used_samples.add(sample)
        used_names[sample] = set()
        count = prompt('Number of paired FASTQ inputs/lanes', positive_int, 1)
        for number in range(1, count + 1):
            print('Pair {}/{}'.format(number, count))

            def unique_pair(value):
                value = identifier(value)
                if value in used_pairs:
                    raise ValueError('Pair identifier already used: ' + value)
                return value

            pair_id = prompt('Pair identifier', unique_pair, '{}_pair{}'.format(sample, number))
            used_pairs.add(pair_id)

            def unused_fastq(value):
                path = readable_file(value, ('.fastq.gz', '.fq.gz'))
                stat = path.stat()
                if (stat.st_dev, stat.st_ino) in used_fastqs:
                    raise ValueError('This FASTQ was already selected.')
                if path.name in used_names[sample]:
                    raise ValueError('FASTQs within a sample need distinct file names.')
                return str(path)

            r1 = prompt('R1 FASTQ (.fastq.gz or .fq.gz)', unused_fastq)
            stat = Path(r1).stat()
            used_fastqs.add((stat.st_dev, stat.st_ino))
            used_names[sample].add(Path(r1).name)
            r2 = prompt('R2 FASTQ (.fastq.gz or .fq.gz)', unused_fastq)
            stat = Path(r2).stat()
            used_fastqs.add((stat.st_dev, stat.st_ino))
            used_names[sample].add(Path(r2).name)
            rows.append(dict(zip(SHEET_COLUMNS, [sample, role, pair_id, r1, r2])))
    rows = validate_samples(rows)
    print('\nReference resources (already available on this server)')
    fasta = prompt('Uncompressed reference FASTA', lambda s: str(reference_bundle(s)[0]))
    assembly = prompt('Assembly (GRCh38 or GRCh37; use GRCh37 for the hg19 assembly family)',
                      assembly_name, 'GRCh38')
    count = prompt('Number of known-sites VCFs', positive_int, 3)
    sites = []
    for number in range(1, count + 1):
        def site_path(value):
            path = readable_file(value, ('.vcf.gz',))
            readable_file(str(path) + '.tbi')
            if str(path) in sites:
                raise ValueError('This known-sites VCF was already selected.')
            return str(path)
        sites.append(prompt('Known-sites VCF {}/{}'.format(number, count), site_path))
    cache = prompt('VEP cache root (contains homo_sapiens/113_{})'.format(assembly),
                   lambda s: str(cache_directory(s, assembly, 113)))
    print('\nTrimming')
    mode = 'auto' if yes_no('Use automatic adapter detection?', default=True) else 'custom'
    adapters = {'adapter_r1': None, 'adapter_r2': None}
    if mode == 'custom':
        adapters = {key: prompt(label, adapter_sequence) for key, label in
                    [('adapter_r1', 'R1 adapter sequence'), ('adapter_r2', 'R2 adapter sequence')]}
    quality = prompt('Quality cutoff', lambda s: positive_int(s, 0, 93), 20)
    minimum = prompt('Minimum retained read length (bp)', positive_int, 20)
    print('\nGPUs: enter the physical GPU indices you are allowed to use. This configuration does not reserve GPUs.')
    align_gpus = prompt('Alignment GPU indices', devices)
    bqsr_gpu = prompt('ApplyBQSR GPU index', lambda s: positive_int(s, 0), align_gpus[0])
    caller_gpus = prompt('Variant-calling GPU indices', devices, ','.join(map(str, align_gpus[:2])))
    resources = {stage: dict(values) for stage, values in DEFAULT_RESOURCES.items()}
    resources['alignment']['gpu_devices'] = align_gpus
    resources['bqsr']['gpu_devices'] = [bqsr_gpu]
    resources['calling']['gpu_devices'] = caller_gpus
    print('\nCPU, memory and thread settings from the HG008 configuration:')
    for stage, values in DEFAULT_RESOURCES.items():
        print('  {}: {}'.format(stage, ', '.join('{}={}'.format(k, v) for k, v in values.items())))
    print('CPU limits are container quotas, not tool thread parameters. Trim Galore 0.4.4 does not become multi-core merely by increasing its CPU quota.')
    if not yes_no('Keep these CPU, memory and thread settings?', default=True):
        for stage, values in DEFAULT_RESOURCES.items():
            print('\n' + stage.replace('_', ' ').capitalize())
            for key, value in values.items():
                resources[stage][key] = prompt(key.replace('_', ' '), positive_int, value)
    return validate_configuration({
        'schema_version': SCHEMA_VERSION, 'analysis_dir': root, 'samples': rows,
        'reference': {'fasta': fasta, 'assembly': assembly, 'known_sites': sites,
                      'vep_cache_dir': cache, 'vep_cache_version': 113},
        'trimming': {'adapter_mode': mode, **adapters, 'quality': quality, 'min_read_length': minimum},
        'resources': resources,
    })


def save_configuration(config, estimate, summary):
    # Exclusive folder creation is the commit point. Nothing is created on cancel.
    root = Path(new_destination(config['analysis_dir']))
    root.mkdir(mode=0o700, exist_ok=False)
    for directory in ('results', 'reports', 'work'):
        (root / directory).mkdir(mode=0o700)
    with (root / 'brisance.json').open('x') as handle:
        json.dump(config, handle, indent=2)
        handle.write('\n')
    with (root / 'samplesheet.csv').open('x', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(config['samples'])
    with (root / 'reports/configuration-summary.txt').open('x') as handle:
        handle.write(summary + '\n')
    with (root / 'reports/storage-estimate.json').open('x') as handle:
        json.dump({'observed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   **estimate}, handle, indent=2)
        handle.write('\n')
    return root


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', metavar='BRISANCE_JSON', help='Validate a saved configuration without writing or starting analysis.')
    mode.add_argument('--preflight', action='store_true', help='After saving, run environment checks; request consent before each missing-image download. Does not start analysis.')
    parser.add_argument('--java', help='Java executable for --preflight only.')
    parser.add_argument('--nextflow', help='Nextflow 26.04.6 executable for --preflight only.')
    parser.add_argument('--no-download', action='store_true', help='For --preflight: refuse missing/wrong images without offering downloads.')
    args = parser.parse_args(argv)
    if not args.preflight and (args.java or args.nextflow or args.no_download):
        parser.error('--java, --nextflow and --no-download require --preflight.')
    try:
        if args.check:
            with Path(args.check).open() as handle:
                config = validate_configuration(json.load(handle))
            estimate = storage_estimate(config)
            print(execution_summary(config, estimate))
            print('\nCONFIGURATION CHECK OK. No processing started; nothing written.')
            return 0
        if not sys.stdin.isatty():
            raise ValueError('Configuration requires an interactive terminal. Use --check to validate saved settings without prompts.')
        config = collect_configuration()
        estimate = storage_estimate(config)
        summary = execution_summary(config, estimate)
        print('\n' + summary + '\n')
        if not yes_no('Save this configuration?', default=False):
            print('Cancelled. No analysis folder created; inputs unchanged.')
            return 0
        root = save_configuration(config, estimate, summary)
        print('\nConfiguration saved: ' + str(root / 'brisance.json'))
        if args.preflight:
            print('Starting environment checks only. No scientific analysis will be started.', flush=True)
            command = [sys.executable, '-B', str(Path(__file__).with_name('check_environment.py')), str(root / 'brisance.json')]
            for flag, value in [('--java', args.java), ('--nextflow', args.nextflow)]:
                if value:
                    command += [flag, value]
            if args.no_download:
                command.append('--no-download')
            return subprocess.run(command, check=False).returncode
        print('No analysis started. The saved configuration must be connected to the parameterized workflow before execution.')
        return 0
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled. No processing started.', file=sys.stderr)
        return 130
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
