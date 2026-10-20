#!/usr/bin/env python3
"""Print reconstructed historical HG008 commands. Never execute scientific work."""
import argparse
from pathlib import Path
import shlex

PB = 'nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1'
REF = 'GRCh38_GIABv3_no_alt_analysis_set_maskedGRC_decoys_MAP2K3_KMT2C_KCNJ18.fasta'
KNOWN = ('Mills_and_1000G_gold_standard.indels.hg38.vcf.gz',
         'Homo_sapiens_assembly38.known_indels.vcf.gz',
         '1000G_phase1.snps.high_confidence.hg38.vcf.gz')
TUMOR = ('HJVHNDSX7-1-IDUDI0031_S12_L001', 'HM22JDSX7-2-IDUDI0031_S12_L002',
         'HM2CNDSX7-2-IDUDI0031_S26_L002', 'HVWWFDSX7-2-IDUDI0031_S138_L002')
NORMAL = 'HV5TMDSX7-1-IDUDI0034_S1_L001'
PREFIX = 'HG008-IDUDI0031_somatico_vs_germinativo'
STAGES = ('trim', 'align-tumor', 'align-normal', 'bqsr-normal', 'bqsr-tumor',
          'read-groups', 'call', 'filter', 'annotate', 'tlod')


def quote(args):
    return ' '.join(shlex.quote(str(arg)) for arg in args)


def recipe(base, cache, stage, tumor_gpu=7, normal_gpu=6):
    base = Path(base)
    cache = Path(cache)
    if not base.is_absolute() or not cache.is_absolute():
        raise ValueError('--base and --cache must be absolute paths')
    if any(',' in str(p) or '\n' in str(p) for p in (base, cache)):
        raise ValueError('Commas/newlines are not supported in mount paths')
    if stage not in STAGES and stage != 'all':
        raise ValueError('Unknown stage')
    if tumor_gpu < 0 or normal_gpu < 0:
        raise ValueError('GPU indices must be nonnegative')

    def path(relative):
        return '/project/' + relative

    def docker(image, command, output, gpu=None, cache_mount=False, env=None):
        args = ['docker', 'run', '--rm', '--pull', 'never']
        if gpu is not None:
            args += ['--gpus', 'device=' + str(gpu)]
        args += ['--workdir', '/project', '-v', str(base) + ':/project:ro',
                 '-v', str(base / output) + ':' + path(output),
                 '-v', str(base / 'tmp') + ':/project/tmp']
        if cache_mount:
            args += ['-v', str(cache) + ':/cache:ro']
        for item in env or []:
            args += ['-e', item]
        # This is printed literally, so the eventual invoking server chooses UID/GID.
        return quote(args) + ' --user "$(id -u):$(id -g)" ' + quote([image] + command)

    def guard(relative):
        p = quote([str(base / relative)])
        return 'test ! -e ' + p + ' && test ! -L ' + p

    def section(name, output, commands, outputs):
        if stage not in ('all', name):
            return []
        return ['\n# ' + name,
                quote(['mkdir', '-p', str(base / output), str(base / 'tmp')]),
                *[guard(out) for out in outputs], *commands]

    lines = ['#!/usr/bin/env bash', 'set -euo pipefail',
             '# RECONSTRUCTED RECIPE: generated only; no processing has started.',
             '# Review inputs, image identity, permissions, storage and GPU availability.']
    cmds, outputs = [], []
    for role, pairs in [('HG008_somatic', TUMOR), ('HG008_germline', (NORMAL,))]:
        for pair in pairs:
            args = ['trim_galore', '--paired', '--quality', '20', '--length', '20',
                    '--fastqc', '-o', path('trimmed')]
            args += [path('raw/' + role + '/' + pair + '_R' + str(mate) + '_001.fastq.gz')
                     for mate in (1, 2)]
            cmds.append(docker('biowardrobe2/trimgalore:v0.4.4', args, 'trimmed',
                               env=['_JAVA_OPTIONS=-Xmx100g']))
            outputs += ['trimmed/' + pair + '_R1_001_val_1.fq.gz',
                        'trimmed/' + pair + '_R2_001_val_2.fq.gz']
    # Historical trimming also had a 100g container cap, but no CPU quota.
    cmds = [command.replace(' --workdir ', ' --memory 100g --workdir ', 1) for command in cmds]
    lines += section('trim', 'trimmed', cmds, outputs)

    for role, pairs, gpu in [('tumor', TUMOR, tumor_gpu), ('normal', (NORMAL,), normal_gpu)]:
        stem = 'HG008-IDUDI0031-' + ('somatico-tentativa2' if role == 'tumor' else 'germinativo')
        args = ['pbrun', 'fq2bam', '--ref', path('reference/' + REF)]
        for pair in pairs:
            args += ['--in-fq', path('trimmed/' + pair + '_R1_001_val_1.fq.gz'),
                     path('trimmed/' + pair + '_R2_001_val_2.fq.gz')]
        for known in KNOWN:
            args += ['--knownSites', path('known-sites/' + known)]
        args += ['--out-bam', path('aligned/' + stem + '.bam'),
                 '--out-recal-file', path('aligned/' + stem + '.recal.table'),
                 '--out-duplicate-metrics', path('aligned/' + stem + '.dup_metrics.txt')]
        if role == 'tumor':
            args += ['--tmp-dir', '/project/tmp']
        args += ['--gpusort', '--gpuwrite']
        lines += section('align-' + role, 'aligned', [docker(PB, args, 'aligned', gpu)],
                         ['aligned/' + stem + suffix for suffix in ('.bam', '.recal.table', '.dup_metrics.txt')])
        bqsr_args = ['pbrun', 'applybqsr', '--ref', path('reference/' + REF),
                     '--in-bam', path('aligned/' + stem + '.bam'),
                     '--in-recal-file', path('aligned/' + stem + '.recal.table'),
                     '--out-bam', path('recalibrated/' + stem + '.bqsr.bam'),
                     '--num-gpus', '1', '--num-threads', '16', '--tmp-dir', '/project/tmp']
        bqsr_gpu = normal_gpu if role == 'tumor' else tumor_gpu
        lines += section('bqsr-' + role, 'recalibrated',
                         [docker(PB, bqsr_args, 'recalibrated', bqsr_gpu)],
                         ['recalibrated/' + stem + '.bqsr.bam'])

    cmds, outputs = [], []
    for name, source in [('somatico', 'somatico-tentativa2'), ('germinativo', 'germinativo')]:
        before = path('recalibrated/HG008-IDUDI0031-' + source + '.bqsr.bam')
        after = path('read_groups/HG008-IDUDI0031-' + name + '_reheader.bam')
        transform = 'sed -E "/^@RG/ s/SM:[^[:space:]]+/SM:' + name + '/g"'
        shell = quote(['samtools', 'reheader', '-c', transform, before]) + ' > ' + quote([after])
        shell += '\n' + quote(['samtools', 'index', '-@', '8', after])
        cmds.append(docker('staphb/samtools:1.19', ['bash', '-euc', shell], 'read_groups'))
        outputs += ['read_groups/HG008-IDUDI0031-' + name + '_reheader.bam']
    lines += section('read-groups', 'read_groups', cmds, outputs)

    args = ['pbrun', 'mutectcaller', '--num-htvc-threads', '32',
            '--ref', path('reference/' + REF),
            '--in-tumor-bam', path('read_groups/HG008-IDUDI0031-somatico_reheader.bam'),
            '--in-normal-bam', path('read_groups/HG008-IDUDI0031-germinativo_reheader.bam'),
            '--out-vcf', path('variants/' + PREFIX + '.vcf'),
            '--tumor-name', 'somatico', '--normal-name', 'germinativo', '--tmp-dir', '/project/tmp']
    lines += section('call', 'variants', [docker(PB, args, 'variants', tumor_gpu)],
                     ['variants/' + PREFIX + '.vcf', 'variants/' + PREFIX + '.vcf.stats'])

    raw, filtered, passed = [path('filtered/' + PREFIX + '.' + suffix + '.vcf.gz')
                             for suffix in ('raw.bgz', 'filtered', 'PASS')]
    compress = quote(['bgzip', '-c', path('variants/' + PREFIX + '.vcf')]) + ' > ' + quote([raw])
    compress += '\n' + quote(['tabix', '-p', 'vcf', raw])
    cmds = [docker('quay.io/biocontainers/htslib:1.19.1--h81da01d_0', ['bash', '-euc', compress], 'filtered'),
            docker('broadinstitute/gatk:4.6.2.0', ['gatk', 'FilterMutectCalls', '-V', raw,
                   '-R', path('reference/' + REF), '--stats', path('variants/' + PREFIX + '.vcf.stats'),
                   '-O', filtered, '--create-output-variant-index', 'true'], 'filtered'),
            docker('staphb/bcftools:1.21', ['bcftools', 'view', '-f', 'PASS', '-Oz', '-o', passed, filtered], 'filtered'),
            docker('staphb/bcftools:1.21', ['bcftools', 'index', '-t', passed], 'filtered')]
    lines += section('filter', 'filtered', cmds,
                     ['filtered/' + PREFIX + '.' + suffix + '.vcf.gz' for suffix in ('raw.bgz', 'filtered', 'PASS')])

    annotated = path('annotated/' + PREFIX + '.PASS_annotado.vep.vcf.gz')
    args = ['vep', '--input_file', passed, '--output_file', annotated, '--species', 'homo_sapiens',
            '--assembly', 'GRCh38', '--format', 'vcf', '--vcf', '--compress_output', 'bgzip',
            '--force_overwrite', '--offline', '--cache', '--dir_cache', '/cache', '--cache_version', '113',
            '--everything', '--fork', '8', '--dir_plugins', '/cache/plugins',
            '--stats_file', path('annotated/' + PREFIX + '.PASS_annotado.vep.stats.html')]
    lines += section('annotate', 'annotated',
                     [docker('ensemblorg/ensembl-vep:release_113.0', args, 'annotated', cache_mount=True),
                      docker('staphb/bcftools:1.21', ['bcftools', 'index', '-t', annotated], 'annotated')],
                     ['annotated/' + PREFIX + '.PASS_annotado.vep.vcf.gz'])
    final = path('final/' + PREFIX + '.PASS_TLOD.vcf.gz')
    lines += section('tlod', 'final',
                     [docker('staphb/bcftools:1.21', ['bcftools', 'view', '-i', 'INFO/TLOD>0 && INFO/TLOD!="."',
                             '-Oz', '-o', final, annotated], 'final'),
                      docker('staphb/bcftools:1.21', ['bcftools', 'index', '-t', final], 'final')],
                     ['final/' + PREFIX + '.PASS_TLOD.vcf.gz'])
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--cache', required=True)
    parser.add_argument('--stage', choices=(*STAGES, 'all'), default='all')
    parser.add_argument('--tumor-gpu', type=int, default=7)
    parser.add_argument('--normal-gpu', type=int, default=6)
    args = parser.parse_args()
    try:
        print(recipe(args.base, args.cache, args.stage, args.tumor_gpu, args.normal_gpu), end='')
    except ValueError as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
