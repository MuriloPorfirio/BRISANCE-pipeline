#!/usr/bin/env python3
"""Reconstructed indel-set comparison, added during repository preparation.

The original file with this name was a misnamed summary-table builder. It is
preserved unchanged under provenance/source_snapshots. This implementation is
synthetically tested but has not reproduced the historical HG008 result yet.
"""
import csv
from pathlib import Path
import sys

COLUMNS = ['CHROM', 'POS', 'REF', 'ALT', 'TYPE', 'INDEL_SUBTYPE']


def load_variants(path):
    variants = set()
    with Path(path).open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle, delimiter='\t')
        if not set(COLUMNS).issubset(reader.fieldnames or []):
            raise ValueError('Missing required variant-table columns: ' + str(path))
        for row in reader:
            if row['TYPE'] != 'INDEL' or row['INDEL_SUBTYPE'] not in ('INS', 'DEL'):
                raise ValueError('Expected an INDEL-only table: ' + str(path))
            pos = int(row['POS'])
            ref, alt, subtype = row['REF'], row['ALT'], row['INDEL_SUBTYPE']
            if pos < 1 or not ref or not alt or len(ref) == len(alt):
                raise ValueError('Invalid indel record in ' + str(path))
            expected_subtype = 'DEL' if len(ref) > len(alt) else 'INS'
            if subtype != expected_subtype:
                raise ValueError('Inconsistent indel subtype in ' + str(path))
            variants.add((row['CHROM'], pos, ref, alt, 'INDEL', subtype))
    return variants


def summary_for(left, right):
    shared, left_only, right_only = left & right, left - right, right - left
    union = len(left | right)
    pct = lambda count: 100 * count / union if union else 0.0
    return {
        'clara_total': len(left), 'dragen_total': len(right), 'shared': len(shared),
        'clara_only': len(left_only), 'dragen_only': len(right_only),
        'union_total': union, 'shared_pct': pct(len(shared)),
        'clara_only_pct': pct(len(left_only)), 'dragen_only_pct': pct(len(right_only)),
    }


def write_table(path, variants):
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t')
        writer.writerow(COLUMNS)
        writer.writerows(sorted(variants))


def compare(left_path, right_path, output_dir):
    left, right = load_variants(left_path), load_variants(right_path)
    output = Path(output_dir)
    # New behavior is intentionally no-overwrite; do not erase historical output.
    output.mkdir(parents=True, exist_ok=False)
    write_table(output / 'shared_indels.tsv', left & right)
    write_table(output / 'clara_only_indels.tsv', left - right)
    write_table(output / 'dragen_only_indels.tsv', right - left)
    summary = summary_for(left, right)
    with (output / 'summary.txt').open('w', encoding='utf-8') as handle:
        handle.write('category=InDels\n')
        for key, value in summary.items():
            rendered = '{:.2f}'.format(value) if key.endswith('_pct') else str(value)
            handle.write(key + '=' + rendered + '\n')
    with (output / 'subtype_summary.tsv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['subtype', *summary], delimiter='\t')
        writer.writeheader()
        for subtype in ('INS', 'DEL'):
            stats = summary_for({v for v in left if v[-1] == subtype}, {v for v in right if v[-1] == subtype})
            writer.writerow({'subtype': subtype, **stats})
    return summary


def main():
    if len(sys.argv) != 4:
        print('Usage: python3 05_compare_indels.py <clara/indels.tsv> <dragen/indels.tsv> <new_output_dir>', file=sys.stderr)
        return 2
    try:
        summary = compare(*sys.argv[1:])
    except (OSError, ValueError, KeyError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        return 1
    print('Reconstructed indel comparison completed; shared={shared}, clara_only={clara_only}, dragen_only={dragen_only}'.format(**summary))
    return 0


if __name__ == '__main__':
    sys.exit(main())
