#!/usr/bin/env python3
"""TEST DOUBLE ONLY. Produces placeholders, never biological results.

Used with real Nextflow and a fake Docker CLI to test orchestration/parameters.
It must never be installed on a scientific execution PATH.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

name = Path(sys.argv[0]).name
args = sys.argv[1:]
if os.environ.get('BRISANCE_TEST_TOOL_LOG'):
    with open(os.environ['BRISANCE_TEST_TOOL_LOG'], 'a') as handle:
        handle.write(json.dumps({'tool': name, 'args': args}) + '\n')


def value(flag):
    return args[args.index(flag) + 1]


def placeholder(path):
    Path(path).write_text('TEST DOUBLE OUTPUT — NOT SCIENTIFIC DATA\n')


if name == 'docker':
    # Test transport only: record generated Docker arguments, then execute the
    # task shell on this host. No Docker socket/daemon, GPU or image is used.
    if args and args[0] == 'run':
        image_index = next((i for i, arg in enumerate(args) if re.fullmatch(r'sha256:[0-9a-f]{64}', arg)), None)
        if image_index is None:
            raise SystemExit('Fake Docker refuses unpinned/missing image IDs')
        raise SystemExit(subprocess.run(args[image_index + 1:], check=False).returncode)
    elif args and args[0] in ('rm', 'stop', 'kill'):
        pass
    else:
        raise SystemExit('Unhandled fake Docker command: ' + repr(args))
elif '--version' in args or '--help' in args:
    print('TEST DOUBLE ONLY: ' + name)
elif name == 'trim_galore':
    for number, raw in enumerate(args[-2:], 1):
        base = re.sub(r'\.(fastq|fq)\.gz$', '', Path(raw).name) + '_val_' + str(number)
        placeholder(base + '.fq.gz')
        placeholder(base + '_fastqc.html')
        placeholder(base + '_fastqc.zip')
        placeholder(Path(raw).name + '_trimming_report.txt')
elif name == 'pbrun':
    for flag in ('--out-bam', '--out-recal-file', '--out-duplicate-metrics', '--out-vcf'):
        if flag in args:
            placeholder(value(flag))
    if '--out-bam' in args:
        placeholder(value('--out-bam') + '.bai')
    if '--out-vcf' in args:
        placeholder(value('--out-vcf') + '.stats')
elif name == 'samtools':
    if args[0] == 'view':
        sample = Path(args[-1]).name.split('.')[0] if '.reheader.' in args[-1] else 'sample'
        print('@HD\tVN:1.6\tSO:coordinate\n@RG\tID:test\tSM:' + sample)
    elif args[0] == 'reheader':
        print('TEST DOUBLE BAM CONTENT')
    elif args[0] == 'index':
        placeholder(args[-1] + '.bai')
    elif args[0] != 'quickcheck':
        raise SystemExit('Unhandled fake samtools command')
elif name == 'bcftools':
    if args[0] == 'index':
        placeholder(args[-1] + '.tbi')
    elif args[0] == 'view':
        if '-h' in args:
            print('##INFO=<ID=CSQ,Number=.,Type=String,Description="Test double">')
        elif '-o' in args:
            placeholder(value('-o'))
        elif '-H' not in args:
            raise SystemExit('Unhandled fake bcftools view')
    else:
        raise SystemExit('Unhandled fake bcftools command')
elif name == 'gatk':
    path = value('-O')
    for suffix in ('', '.tbi', '.filteringStats.tsv'):
        placeholder(path + suffix)
elif name == 'vep':
    placeholder(value('--output_file'))
    placeholder(value('--stats_file'))
else:
    raise SystemExit('Unhandled test double: ' + name)
