#!/usr/bin/env python3
"""TEST DOUBLE ONLY. Produces placeholders, never biological results.

Used with real Nextflow and a fake Docker CLI to test orchestration/parameters.
It must never be installed on a scientific execution PATH.
"""
import json
import io
import itertools
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile

name = Path(sys.argv[0]).name
args = sys.argv[1:]
if os.environ.get('BRISANCE_TEST_TOOL_LOG'):
    with open(os.environ['BRISANCE_TEST_TOOL_LOG'], 'a') as handle:
        handle.write(json.dumps({'tool': name, 'args': args}) + '\n')


def value(flag):
    return args[args.index(flag) + 1]


def placeholder(path):
    Path(path).write_text('TEST DOUBLE OUTPUT — NOT SCIENTIFIC DATA\n')


def synthetic_priors(path, sample):
    columns = ['context', 'rev_comp'] + ['f1r2_' + b for b in 'acgt'] + ['f2r1_' + b for b in 'acgt'] + [
        'hom_ref', 'germline_het', 'somatic_het', 'hom_var', 'num_examples', 'num_alt_examples']
    text = '#<METADATA>SAMPLE=' + sample + '\n' + '\t'.join(columns) + '\n'
    for bases in itertools.product('ACGT', repeat=3):
        context = ''.join(bases)
        text += '\t'.join([context, context.translate(str.maketrans('ACGT', 'TGCA'))[::-1]] +
                          ['0'] * 8 + ['1', '0', '0', '0', '0', '0']) + '\n'
    payload = text.encode()
    with tarfile.open(path, 'w:gz') as archive:
        member = tarfile.TarInfo(sample + '.orientation_priors')
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))


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
    for flag in ('--out-bam', '--out-recal-file', '--out-duplicate-metrics', '--out-vcf', '--mutect-f1r2-tar-gz'):
        if flag in args:
            if flag == '--mutect-f1r2-tar-gz' and os.environ.get('BRISANCE_TEST_OMIT_F1R2'):
                continue
            placeholder(value(flag))
    if args[0] == 'prepon':
        placeholder(value('--in-pon-file') + '.pon')
    if '--out-qc-metrics-dir' in args:
        Path(value('--out-qc-metrics-dir')).mkdir(parents=True, exist_ok=True)
        placeholder(Path(value('--out-qc-metrics-dir')) / 'alignment_metrics.txt')
    if '--out-bam' in args:
        placeholder(value('--out-bam') + '.bai')
    if '--out-vcf' in args:
        placeholder(value('--out-vcf') + '.stats')
elif name == 'samtools':
    if args[0] == 'view' and '-c' in args:
        print('0')
    elif args[0] == 'view':
        sample = Path(args[-1]).name.split('.')[0] if '.reheader.' in args[-1] else 'sample'
        if Path(args[-1]).name == 'input.bam' or Path(args[-1]).name in ('TUMOR.bam', 'NORMAL.bam'):
            sample = Path(args[-1]).resolve().stem
        print('@HD\tVN:1.6\tSO:coordinate\n@SQ\tSN:chr1\tLN:100\n@RG\tID:test\tSM:' + sample)
    elif args[0] == 'reheader':
        print('TEST DOUBLE BAM CONTENT')
    elif args[0] == 'index':
        placeholder(args[-1] + '.bai')
    elif args[0] != 'quickcheck':
        raise SystemExit('Unhandled fake samtools command')
elif name == 'bcftools':
    if args[0] == 'index':
        if '-n' in args:
            print('1' if Path(args[-1]).name == 'population.vcf.gz' else '0')
        elif '-s' in args:
            print('chr1\t100\t1')
        else:
            placeholder(args[-1] + '.tbi')
    elif args[0] == 'reheader':
        placeholder(value('-o'))
    elif args[0] == 'norm':
        pass
    elif args[0] == 'query':
        if '-f' in args:
            print('chr1\t1\tA\tC\t0.1')
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
    if 'LearnReadOrientationModel' in args:
        synthetic_priors(path, Path(path).name.split('.')[0])
    elif 'CalculateContamination' in args:
        sample = Path(path).name.split('.')[0]
        Path(path).write_text('sample\tcontamination\terror\n' + sample + '\t0.001\t0.0001\n')
        Path(value('--tumor-segmentation')).write_text('#<METADATA>SAMPLE=' + sample +
            '\ncontig\tstart\tend\tminor_allele_fraction\nchr1\t1\t100\t0.5\n')
    elif 'GetPileupSummaries' in args:
        placeholder(path)
    else:
        for flag in ('--orientation-bias-artifact-priors', '--contamination-table', '--tumor-segmentation'):
            if flag in args and not Path(value(flag)).is_file():
                raise SystemExit('Missing staged model: ' + value(flag))
        for suffix in ('', '.tbi', '.filteringStats.tsv'):
            placeholder(path + suffix)
elif name == 'vep':
    placeholder(value('--output_file'))
    placeholder(value('--stats_file'))
else:
    raise SystemExit('Unhandled test double: ' + name)
