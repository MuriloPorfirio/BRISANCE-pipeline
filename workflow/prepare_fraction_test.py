#!/usr/bin/env python3
"""Prepare an independently sampled fraction of every paired FASTQ CSV row.

Default is metadata-only dry run. --execute reads the full sources; no Nextflow
processing is started. The original FASTQs are mounted read-only in Docker.
"""

import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from prepare_trim_test import COLUMNS


IMAGE = 'staphb/seqtk@sha256:82797114adb664ba939b4f6dfcb822483a4af827def4288e5207be559055f2cc'
SAFE_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*\Z')
SAMPLING_SCRIPT = 'gzip -dc -- "$1" | seqtk sample -s"$2" - "$3" | gzip -1 -n > "$4"'
RESERVE_BYTES = 100 * 1024 ** 3


def stamp():
    return datetime.now(timezone.utc).isoformat()


def identity(path):
    info = path.stat()
    return {'path': str(path), 'bytes': info.st_size, 'mtime_ns': info.st_mtime_ns,
            'device': info.st_dev, 'inode': info.st_ino}


def load_rows(input_csv):
    with Path(input_csv).open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f'Expected columns: {",".join(COLUMNS)}')
        rows = list(reader)
    if not rows:
        raise ValueError('Empty samplesheet')
    pair_ids, sources, role_samples = set(), set(), {}
    for row in rows:
        if set(row) != set(COLUMNS) or any(not isinstance(row[key], str) for key in COLUMNS):
            raise ValueError('Malformed samplesheet row')
        for key in COLUMNS:
            row[key] = row[key].strip()
        if not all(SAFE_NAME.fullmatch(row[key]) for key in ('sample', 'pair_id')):
            raise ValueError('Unsafe sample or pair identifier')
        if row['pair_id'] in pair_ids:
            raise ValueError('Duplicate pair_id')
        pair_ids.add(row['pair_id'])
        if row['role'] not in ('tumor', 'normal'):
            raise ValueError('Role must be tumor or normal')
        role_samples.setdefault(row['role'], set()).add(row['sample'])
        for key in ('fastq_1', 'fastq_2'):
            path = Path(row[key])
            if not path.is_absolute():
                raise ValueError('FASTQ paths must be absolute')
            path = path.resolve(strict=True)
            if not path.is_file() or path.stat().st_size == 0 or not os.access(path, os.R_OK):
                raise ValueError(f'Missing, empty or unreadable FASTQ: {path}')
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:fastq|fq)\.gz', path.name):
                raise ValueError(f'Unsupported FASTQ basename: {path.name}')
            if any(c in str(path.parent) for c in (',', '\n', '\r')):
                raise ValueError('Input directory is not supported by Docker bind syntax')
            if path in sources:
                raise ValueError('A FASTQ was reused in the samplesheet')
            sources.add(path)
            row[key] = str(path)
        if Path(row['fastq_1']).name == Path(row['fastq_2']).name:
            raise ValueError('R1 and R2 must have distinct basenames')
    if set(role_samples) != {'tumor', 'normal'} or any(len(s) != 1 for s in role_samples.values()):
        raise ValueError('Provide exactly one tumor and one normal sample, possibly with multiple pairs')
    if role_samples['tumor'] == role_samples['normal']:
        raise ValueError('Tumor and normal identifiers must differ')
    return rows


def pair_seed(seed, pair_id):
    digest = hashlib.sha256(f'{seed}:{pair_id}'.encode('ascii')).digest()
    return 1 + int.from_bytes(digest[:4], 'big') % 2147483646


def docker_base():
    return ['docker', 'run', '--rm', '--pull', 'never', '--user', f'{os.getuid()}:{os.getgid()}',
            '--cpus', '2', '--memory', '2g', '--entrypoint', '/bin/bash']


def probe_tools():
    result = subprocess.run(docker_base() + [IMAGE, '-euo', 'pipefail', '-c',
        'command -v seqtk; command -v gzip; gzip --version; '
        'if seqtk; then :; else test "$?" -eq 1; fi'],
        check=True, capture_output=True, text=True)
    output = result.stdout + result.stderr
    if 'Version: 1.4-r122' not in output:
        raise RuntimeError('Unexpected seqtk version; expected 1.4-r122')
    return output


def sample_mate(source, destination, seed, fraction, log):
    command = docker_base() + [
        '--mount', f'type=bind,source={source.parent},target=/input,readonly',
        '--mount', f'type=bind,source={destination.parent},target=/output',
        IMAGE, '-euo', 'pipefail', '-c', SAMPLING_SCRIPT,
        'brisance-sample', '/input/' + source.name, str(seed), str(fraction),
        '/output/' + destination.name]
    with log.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(command) + '\n')
        handle.flush()
        subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, check=True)


def record(stream, path, number, mate):
    header = stream.readline()
    if not header:
        return None
    sequence, plus, quality = stream.readline(), stream.readline(), stream.readline()
    if not all((sequence, plus, quality)):
        raise ValueError(f'{path}: incomplete FASTQ record {number}')
    if not header.startswith(b'@') or not plus.startswith(b'+'):
        raise ValueError(f'{path}: invalid FASTQ structure at record {number}')
    seq, qual = sequence.rstrip(b'\r\n'), quality.rstrip(b'\r\n')
    if not seq or len(seq) != len(qual):
        raise ValueError(f'{path}: sequence/quality mismatch at record {number}')
    words = header[1:].split()
    if not words:
        raise ValueError(f'{path}: missing read identifier')
    identifier = words[0]
    if identifier.endswith((b'/1', b'/2')):
        if not identifier.endswith(f'/{mate}'.encode()):
            raise ValueError(f'{path}: wrong mate suffix at record {number}')
        identifier = identifier[:-2]
    if len(words) > 1 and re.match(rb'[12]:', words[1]):
        if not words[1].startswith(f'{mate}:'.encode()):
            raise ValueError(f'{path}: wrong Illumina mate field at record {number}')
    return identifier, (header, sequence, plus, quality)


def verify_pair(paths):
    count = 0
    hashes = [hashlib.sha256(), hashlib.sha256()]
    with gzip.open(paths[0], 'rb') as r1, gzip.open(paths[1], 'rb') as r2:
        while True:
            a, b = record(r1, paths[0], count + 1, 1), record(r2, paths[1], count + 1, 2)
            if a is None and b is None:
                break
            if a is None or b is None:
                raise ValueError('Sampled R1/R2 have different record counts')
            if a[0] != b[0]:
                raise ValueError(f'Sampled mate identifiers differ at record {count + 1}')
            for digest, item in zip(hashes, (a, b)):
                digest.update(b''.join(item[1]))
            count += 1
            if count % 1000000 == 0:
                print(f'  Verified {count:,} synchronized selected pairs', flush=True)
    if count == 0:
        raise ValueError('Sampling produced no read pairs')
    return count, [digest.hexdigest() for digest in hashes]


def save_manifest(target, manifest):
    path = target / 'manifest.json.partial'
    with path.open('w', encoding='utf-8') as handle:
        json.dump(manifest, handle, indent=2)
        handle.write('\n')
    path.replace(target / 'manifest.json')


def prepare(input_csv, output_root, fraction=0.2, seed=42, execute=False):
    if not math.isfinite(fraction) or not 0 < fraction < 1:
        raise ValueError('Fraction must be strictly between 0 and 1 (e.g. 0.2)')
    if not 1 <= seed <= 2147483646:
        raise ValueError('Seed must be between 1 and 2147483646')
    rows = load_rows(input_csv)
    snapshots = {value: identity(Path(value)) for row in rows
                 for key, value in row.items() if key in ('fastq_1', 'fastq_2')}
    total_bytes = sum(item['bytes'] for item in snapshots.values())
    output_root = Path(output_root).resolve()
    if any(c in str(output_root) for c in (',', '\n', '\r')):
        raise ValueError('Output directory is not supported by Docker bind syntax')
    print(f'Validated {len(rows)} pairs: '
          f'{sum(row["role"] == "tumor" for row in rows)} tumor, '
          f'{sum(row["role"] == "normal" for row in rows)} normal.', flush=True)
    print(f'Requested fraction: {fraction}; base seed: {seed}; source bytes: {total_bytes}', flush=True)
    if not execute:
        print('DRY RUN: metadata only; no FASTQ contents read, Docker run or outputs created.', flush=True)
        return None
    versions = probe_tools()
    output_root.mkdir(parents=True, exist_ok=True)
    # Conservative preparation guard only, not an estimate of later BAM/work space.
    if shutil.disk_usage(output_root).free < 3 * fraction * total_bytes + RESERVE_BYTES:
        raise RuntimeError('Insufficient free space for preparation guard (3x sampled source bytes + 100 GiB reserve)')
    label = format(fraction * 100, '.6g').replace('.', 'p')
    target = Path(tempfile.mkdtemp(prefix=f'hg008-{label}pct-', dir=output_root))
    manifest = {'status': 'in_progress', 'started_utc': stamp(), 'purpose': 'Subsampled functional WGS test; not historical benchmarking',
        'requested_fraction': fraction, 'base_seed': seed, 'image': IMAGE,
        'seed_derivation': '1 + uint32_be(SHA256(str(base_seed)+":"+pair_id)[0:4]) % 2147483646',
        'method': 'seqtk 1.4 fractional streaming sample; same seed for both mates; all CSV rows',
        'compression': 'gzip -1 -n; decompression CRC errors propagate via bash pipefail',
        'limits': 'one mate at a time; container 2 CPU quota, 2 GiB RAM; no GPU',
        'source_samplesheet': str(Path(input_csv).resolve()), 'source_rows': rows,
        'source_metadata': snapshots, 'completed_pairs': [],
        'limitations': 'Requested fraction is probabilistic, not exact; original full FASTQ pairing/structure and source SHA256 are not established by metadata. Selected pairs are fully checked. Source FASTQ formatting may be rewritten by seqtk. Read-only binds protect sources from these containers.'}
    save_manifest(target, manifest)
    (target / 'tool_versions.txt').write_text(versions, encoding='utf-8')
    print(f'Output directory: {target}', flush=True)
    started = time.monotonic()
    try:
        sampled_rows = []
        for ordinal, row in enumerate(rows, 1):
            print(f'[{ordinal}/{len(rows)}] {row["sample"]}: {row["pair_id"]}', flush=True)
            directory = target / row['sample'] / row['pair_id']
            directory.mkdir(parents=True)
            sources = [Path(row[key]) for key in ('fastq_1', 'fastq_2')]
            destinations = [directory / source.name for source in sources]
            partials = [directory / ('.' + source.name + '.partial') for source in sources]
            derived_seed = pair_seed(seed, row['pair_id'])
            pair_started = time.monotonic()
            for mate, (source, partial) in enumerate(zip(sources, partials), 1):
                if identity(source) != snapshots[str(source)]:
                    raise RuntimeError(f'Source changed before sampling: {source}')
                if shutil.disk_usage(target).free < 3 * fraction * source.stat().st_size + RESERVE_BYTES:
                    raise RuntimeError('Free space fell below preparation guard')
                print(f'  Sampling R{mate}, seed={derived_seed}', flush=True)
                sample_mate(source, partial, derived_seed, fraction, directory / f'R{mate}.sampling.log')
                if identity(source) != snapshots[str(source)]:
                    raise RuntimeError(f'Source changed during sampling: {source}')
            print('  Checking all selected read pairs and gzip integrity', flush=True)
            count, hashes = verify_pair(partials)
            for source, destination in zip(partials, destinations):
                source.replace(destination)
            sampled_rows.append(dict(row, fastq_1=str(destinations[0]), fastq_2=str(destinations[1])))
            manifest['completed_pairs'].append({'pair_id': row['pair_id'], 'sample': row['sample'],
                'role': row['role'], 'seed': derived_seed, 'selected_pairs': count,
                'uncompressed_output_sha256': hashes, 'outputs': [str(path) for path in destinations],
                'output_bytes': [path.stat().st_size for path in destinations],
                'elapsed_seconds': round(time.monotonic() - pair_started, 3)})
            save_manifest(target, manifest)
            print(f'  Completed: {count:,} synchronized pairs', flush=True)
        for value, before in snapshots.items():
            if identity(Path(value)) != before:
                raise RuntimeError(f'Source changed during preparation: {value}')
        pending_sheet = target / 'samplesheet.csv.partial'
        with pending_sheet.open('x', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(sampled_rows)
        manifest.update(status='complete', finished_utc=stamp(), elapsed_seconds=round(time.monotonic() - started, 3))
        save_manifest(target, manifest)
        pending_sheet.replace(target / 'samplesheet.csv')
    except BaseException as exc:
        manifest.update(status='failed', failed_utc=stamp(), error=str(exc))
        save_manifest(target, manifest)
        raise RuntimeError(f'Preparation failed; partial files retained in {target}. Do not use them for processing.') from exc
    sheet = target / 'samplesheet.csv'
    print(f'Samplesheet ready: {sheet}', flush=True)
    print('Original FASTQs preserved; no trimming/alignment/variant calling started.', flush=True)
    return sheet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output-root', required=True, type=Path)
    parser.add_argument('--fraction', type=float, default=0.2)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--execute', action='store_true', help='Read full originals and prepare sampled FASTQs; default is metadata-only')
    args = parser.parse_args()
    prepare(args.input, args.output_root, args.fraction, args.seed, args.execute)


if __name__ == '__main__':
    main()
