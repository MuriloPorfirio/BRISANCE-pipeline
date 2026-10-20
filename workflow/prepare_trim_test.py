#!/usr/bin/env python3
"""Prepare small paired FASTQ prefixes for a functional trimming test only."""

import argparse
import csv
import gzip
import json
from pathlib import Path
import tempfile


COLUMNS = ['sample', 'role', 'pair_id', 'fastq_1', 'fastq_2']


def read_record(stream, source, number):
    lines = [stream.readline() for _ in range(4)]
    if any(not line for line in lines):
        raise ValueError(f'{source}: incomplete or missing FASTQ record {number}')
    header, sequence, plus, quality = [line.rstrip('\r\n') for line in lines]
    if not header.startswith('@') or not plus.startswith('+'):
        raise ValueError(f'{source}: invalid FASTQ structure at record {number}')
    if not sequence or len(sequence) != len(quality):
        raise ValueError(f'{source}: sequence/quality length mismatch at record {number}')
    identifier = header[1:].split()[0]
    if identifier.endswith(('/1', '/2')):
        identifier = identifier[:-2]
    return identifier, lines


def copy_prefix(row, target, count):
    sources = [Path(row[key]).resolve(strict=True) for key in ('fastq_1', 'fastq_2')]
    if sources[0] == sources[1] or sources[0].name == sources[1].name:
        raise ValueError('R1 and R2 must have distinct paths and basenames')
    destination = target / row['role']
    destination.mkdir()
    outputs = [destination / source.name for source in sources]
    with gzip.open(sources[0], 'rt', encoding='ascii', newline='') as r1, \
            gzip.open(sources[1], 'rt', encoding='ascii', newline='') as r2, \
            gzip.open(outputs[0], 'wt', encoding='ascii', newline='') as w1, \
            gzip.open(outputs[1], 'wt', encoding='ascii', newline='') as w2:
        for number in range(1, count + 1):
            id1, lines1 = read_record(r1, sources[0], number)
            id2, lines2 = read_record(r2, sources[1], number)
            if id1 != id2:
                raise ValueError(f"{row['pair_id']}: mate IDs differ at record {number}")
            w1.writelines(lines1)
            w2.writelines(lines2)
    return dict(row, fastq_1=str(outputs[0]), fastq_2=str(outputs[1]))


def prepare(input_csv, output_root, count=10000):
    if not 1 <= count <= 1000000:
        raise ValueError('Use between 1 and 1000000 read pairs per sample')
    with Path(input_csv).open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f'Expected columns: {",".join(COLUMNS)}')
        rows = list(reader)
    selected = []
    for role in ('tumor', 'normal'):
        candidates = [row for row in rows if row['role'] == role]
        if not candidates:
            raise ValueError(f'No {role} FASTQ pair in the samplesheet')
        selected.append(candidates[0])

    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix='trim-test-', dir=root))
    try:
        test_rows = [copy_prefix(row, target, count) for row in selected]
        sheet = target / 'samplesheet.csv'
        with sheet.open('x', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(test_rows)
        manifest = {
            'purpose': 'Functional stage-1 test, not biological benchmarking',
            'selection': 'First CSV pair per role; first N synchronized read pairs',
            'read_pairs_per_sample': count,
            'source_samplesheet': str(Path(input_csv).resolve()),
            'source_rows': selected,
        }
        with (target / 'test_manifest.json').open('x', encoding='utf-8') as stream:
            json.dump(manifest, stream, indent=2)
            stream.write('\n')
    except Exception as exc:
        raise RuntimeError(
            f'Test preparation failed; partial files were retained in {target}. '
            'Do not use that directory for processing.'
        ) from exc
    return sheet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output-root', required=True, type=Path)
    parser.add_argument('--reads', default=10000, type=int,
                        help='Read pairs per sample, default 10000')
    args = parser.parse_args()
    sheet = prepare(args.input, args.output_root, args.reads)
    print(f'Prepared {args.reads} synchronized read pairs per sample (tumor and normal).')
    print(f'Test samplesheet: {sheet}')
    print('Original FASTQs were opened read-only; no trimming has started.')


if __name__ == '__main__':
    main()
