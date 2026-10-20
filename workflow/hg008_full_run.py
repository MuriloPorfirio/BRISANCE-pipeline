#!/usr/bin/env python3
"""Turing-specific full HG008 launcher guards; standard library only.

Never subsets, removes or hashes FASTQ/BAM contents. Scientific modules and
resource settings are unchanged. Storage checks are a best-effort courtesy on
a shared filesystem, not a quota/reservation or a guarantee against overshoot.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
DATASET = 'hg008-100pct'
GPUS = ('7', '6', '5')
CACHE = Path('/home/leticia.santos/vep_data')
IMAGES = ('biowardrobe2/trimgalore:v0.4.4',
          'nvcr.io/nvidia/clara/clara-parabricks:4.5.1-1',
          'staphb/samtools:1.19', 'broadinstitute/gatk:4.6.2.0',
          'staphb/bcftools:1.21', 'ensemblorg/ensembl-vep:release_113.0')
# Size evidence from the user's completed original-FASTQ transfer on Turing.
EXPECTED_PAIRS = {
    'HJVHNDSX7-1-IDUDI0031_S12_L001': ('somatico', 'tumor', 'HG008_somatic', 13067670918, 14070269642),
    'HM22JDSX7-2-IDUDI0031_S12_L002': ('somatico', 'tumor', 'HG008_somatic', 40921939698, 44176562405),
    'HM2CNDSX7-2-IDUDI0031_S26_L002': ('somatico', 'tumor', 'HG008_somatic', 19062888154, 20298224493),
    'HVWWFDSX7-2-IDUDI0031_S138_L002': ('somatico', 'tumor', 'HG008_somatic', 39804061971, 43572350218),
    'HV5TMDSX7-1-IDUDI0034_S1_L001': ('germinativo', 'normal', 'HG008_germline', 129174728987, 136093590644),
}
LIMIT = 0.65
STOP = 0.64
POLL_SECONDS = 15


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def no_symlink(path):
    for part in (path,) + tuple(path.parents):
        if part.is_symlink():
            raise ValueError('Caminho simbólico não permitido: ' + str(part))


def check_paths():
    no_symlink(ROOT)
    for name in ('results', 'work', 'reports'):
        parent = ROOT / name
        no_symlink(parent)
        if parent.exists() and not parent.is_dir():
            raise ValueError('Pasta esperada: ' + str(parent))
    for name in ('results', 'work'):
        target = ROOT / name / DATASET
        if target.exists() or target.is_symlink():
            raise ValueError('Já existe results/work dos 100%; não sobrescrever nem reiniciar: ' + str(target))
    no_symlink(ROOT / 'reports' / DATASET)


def raw_metadata():
    sheet = ROOT / 'hg008_samplesheet.csv'
    no_symlink(sheet)
    with sheet.open(newline='') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ['sample', 'role', 'pair_id', 'fastq_1', 'fastq_2']:
            raise ValueError('Colunas inesperadas no samplesheet original.')
        rows = list(reader)
    if len(rows) != len(EXPECTED_PAIRS) or {row['pair_id'] for row in rows} != set(EXPECTED_PAIRS):
        raise ValueError('Os 100% exigem os cinco pares originais: quatro tumorais e um normal.')
    files = []
    for row in rows:
        sample, role, folder, size1, size2 = EXPECTED_PAIRS[row['pair_id']]
        if row['sample'] != sample or row['role'] != role:
            raise ValueError('Amostra/role inesperado: ' + row['pair_id'])
        for mate, size in ((1, size1), (2, size2)):
            path = ROOT / 'data/raw' / folder / (row['pair_id'] + '_R{}_001.fastq.gz'.format(mate))
            if row['fastq_' + str(mate)] != str(path):
                raise ValueError('O CSV deve apontar diretamente para os originais de 100%: ' + str(path))
            no_symlink(path)
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_size != size or not os.access(path, os.R_OK):
                raise ValueError('FASTQ ausente, ilegível ou tamanho diferente da cópia original: ' + str(path))
            files.append({'path': str(path), 'size': info.st_size, 'mtime_ns': info.st_mtime_ns,
                          'inode': info.st_ino, 'device': info.st_dev})
    return {'samplesheet': str(sheet), 'pairs': len(rows), 'files': files,
            'source_bytes': sum(item['size'] for item in files),
            'verification': 'path_size_mtime_inode_only_NO_FASTQ_CONTENT_HASHES'}


def storage():
    info = os.statvfs(ROOT)
    used = (info.f_blocks - info.f_bfree) * info.f_frsize
    available = info.f_bavail * info.f_frsize
    denominator = used + available
    if denominator <= 0:
        raise ValueError('Não foi possível calcular a ocupação do filesystem.')
    return {'utc': utc(), 'used_bytes': used, 'available_bytes': available,
            'used_fraction': used / denominator}


def require_storage(snapshot):
    if snapshot['used_fraction'] >= STOP:
        raise ValueError('Ocupação em {:.2f}%; limiar de interrupção é 64%, antes do teto solicitado de 65%.'.format(
            100 * snapshot['used_fraction']))


def capture(command, timeout=45):
    result = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    return result.stdout.strip()


def idle_gpus(devices):
    output = capture(['nvidia-smi', '-i', ','.join(devices),
        '--query-gpu=index,uuid,name,memory.total,memory.free,utilization.gpu',
        '--format=csv,noheader,nounits'])
    rows = list(csv.reader(output.splitlines(), skipinitialspace=True))
    found = {}
    for row in rows:
        if len(row) != 6:
            raise ValueError('Resposta inesperada do nvidia-smi.')
        index, uuid, name, total, free, utilization = (value.strip() for value in row)
        if index in found or index not in devices:
            raise ValueError('GPU inesperada/duplicada: ' + index)
        if ('A100' not in name or int(utilization) != 0 or
                int(total) - int(free) > 2048 or int(free) < 75000):
            raise ValueError('GPU {} ocupada ou diferente da configuração A100 80 GB: {}'.format(index, ', '.join(row)))
        found[index] = {'index': index, 'uuid': uuid, 'name': name,
                        'total_mib': int(total), 'free_mib': int(free), 'utilization': int(utilization)}
    if set(found) != set(devices):
        raise ValueError('Não foram encontradas todas as GPUs selecionadas.')
    apps = capture(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader,nounits'])
    selected = {item['uuid'] for item in found.values()}
    for row in csv.reader(apps.splitlines(), skipinitialspace=True):
        if row and row[0].strip() in selected:
            raise ValueError('Há um processo na GPU selecionada: ' + ', '.join(row))
    return [found[index] for index in devices]


def stage_guard(devices):
    require_storage(storage())
    if devices:
        if devices not in (GPUS, ('7',), ('7', '6')):
            raise ValueError('Configuração GPU não permitida no guard.')
        idle_gpus(devices)


def guard_config(path):
    def groovy(value):
        return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"
    prefix = [sys.executable, '-B', str(Path(__file__).resolve()), '--stage-guard']
    stages = {'TRIM_GALORE': (), 'FQ2BAM': GPUS, 'APPLY_BQSR': ('7',),
              'ADJUST_READ_GROUPS': (), 'MUTECT_CALLER': ('7', '6'),
              'COMPRESS_RAW_VCF': (), 'FILTER_MUTECT_CALLS': (), 'SELECT_PASS': (),
              'ANNOTATE_VEP': (), 'INDEX_VEP': (), 'SELECT_POSITIVE_TLOD': ()}
    lines = ['// Launcher safety only: does not change scientific commands/resources.', 'process {']
    for name, devices in stages.items():
        command = shlex.join(prefix + [','.join(devices) if devices else 'none'])
        lines.append('    withName: {} {{ beforeScript = {} }}'.format(name, groovy(command)))
    lines.append('}')
    path.write_text('\n'.join(lines) + '\n')


def nf_command(mode, log, work, config, reports=None):
    command = [str(ROOT / 'nextflow-26.04.6-dist'), '-c', str(config), '-log', str(log),
        'run', str(ROOT / 'workflow/main.nf'), '--mode', mode,
        '--input', str(ROOT / 'hg008_samplesheet.csv'),
        '--outdir', str(ROOT / 'results' / DATASET / 'stage1'),
        '--gpu_devices', '7,6,5', '--bqsr_gpu_device', '7', '--caller_gpu_devices', '7,6',
        '--vep_cache_dir', str(CACHE), '-work-dir', str(work), '-ansi-log', 'false']
    if reports is not None:
        command += ['-with-trace', str(reports / 'trace.tsv'), '-with-report', str(reports / 'report.html'),
                    '-with-timeline', str(reports / 'timeline.html')]
    return command


def preflight(directory):
    check_paths()
    original = raw_metadata()
    print('Originais: {} pares; {} FASTQs; {} bytes. Sem subamostragem.'.format(
        original['pairs'], len(original['files']), original['source_bytes']), flush=True)
    if capture([str(ROOT / 'nextflow-26.04.6-dist'), '-version']).find('version 26.04.6 ') < 0:
        raise ValueError('Este teste mantém exatamente Nextflow 26.04.6.')
    server = capture(['docker', 'version', '--format', '{{.Server.Version}}'])
    images = {}
    for image in IMAGES:
        images[image] = json.loads(capture(['docker', 'image', 'inspect', image,
            '--format', '{"id":{{json .Id}},"digests":{{json .RepoDigests}}}']))
    config = directory / 'launcher-safety.config'
    guard_config(config)
    # Validation uses its own launch/work directory, never the scientific work.
    command = nf_command('validate-annotate', directory / 'preflight-nextflow.log',
                         directory / 'preflight-work', config)
    subprocess.run(command, cwd=directory, check=True, timeout=180)
    # Read cache metadata as the actual numeric container user; no payload scan.
    cache_meta = capture(['docker', 'run', '--rm', '--pull', 'never',
        '--user', '{}:{}'.format(os.getuid(), os.getgid()),
        '--mount', 'type=bind,source={},target=/cache,readonly'.format(CACHE),
        IMAGES[-1], 'bash', '-euo', 'pipefail', '-c',
        'test -r /cache/homo_sapiens/113_GRCh38/info.txt; '
        'grep -E "^(species|assembly)[[:space:]]" /cache/homo_sapiens/113_GRCh38/info.txt'])
    if not (re.search(r'^species\s+homo_sapiens\s*$', cache_meta, re.M) and
            re.search(r'^assembly\s+GRCh38\s*$', cache_meta, re.M)):
        raise ValueError('Metadados VEP inesperados dentro do container.')
    print('Cache VEP acessível dentro do container, somente leitura.', flush=True)
    with Path('/proc/meminfo').open() as handle:
        memory = dict(line.split(':', 1) for line in handle)
    available_ram = int(memory['MemAvailable'].strip().split()[0]) * 1024
    if available_ram < 320 * 2**30:
        raise ValueError('Menos de 320 GiB de RAM disponíveis para esta configuração.')
    gpus = idle_gpus(GPUS)
    visible = capture(['docker', 'run', '--rm', '--pull', 'never', '--gpus', '"device=7,6,5"',
                       IMAGES[1], 'nvidia-smi', '--query-gpu=uuid', '--format=csv,noheader'])
    if {row.strip() for row in visible.splitlines()} != {gpu['uuid'] for gpu in gpus}:
        raise ValueError('GPUs visíveis no container não correspondem às GPUs 7,6,5 do host.')
    snapshot = storage()
    print('Ocupação: {:.2f}%; teto solicitado: 65%; interrupção preventiva: 64%. '
          'Sem exigência de margem inicial em TiB.'.format(100 * snapshot['used_fraction']), flush=True)
    print('GPUs verificadas neste instante; não há reserva de GPUs, RAM ou disco.', flush=True)
    require_storage(snapshot)
    return {'utc': utc(), 'raw': original, 'docker_server': server, 'images': images,
            'gpus': gpus, 'available_ram_bytes': available_ram, 'storage': snapshot,
            'storage_policy': {'minimum_headroom_check': False, 'limit_fraction': LIMIT,
                               'stop_fraction': STOP, 'poll_seconds': POLL_SECONDS},
            'cache_metadata_in_container': cache_meta}


def archive_inputs(reports):
    with tarfile.open(reports / 'execution-inputs.tar.gz', 'w:gz') as archive:
        def exclude_generated(info):
            return None if '__pycache__' in Path(info.name).parts else info
        archive.add(ROOT / 'workflow', arcname='workflow', filter=exclude_generated)
        archive.add(ROOT / 'hg008_samplesheet.csv', arcname='hg008_samplesheet.csv')
        archive.add(reports / 'launcher-safety.config', arcname='launcher-safety.config')
    # Small executable only; never hash the large sequencing data.
    digest = hashlib.sha256()
    with (ROOT / 'nextflow-26.04.6-dist').open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    (reports / 'nextflow.sha256').write_text(digest.hexdigest() + '  nextflow-26.04.6-dist\n')


def monitor(command, reports, interval=POLL_SECONDS):
    # Only this child receives TERM; no broad pkill/docker stop operations.
    process = subprocess.Popen(command, cwd=ROOT, start_new_session=True)
    interrupted = []
    previous = {}
    def request_stop(reason):
        if not interrupted:
            interrupted.append(reason)
            # Do not depend on a writable log filesystem to send the stop signal.
            if process.poll() is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
            print('ATENÇÃO: solicitando interrupção do Nextflow: ' + reason, flush=True)
            try:
                (reports / 'interruption.json').write_text(json.dumps({'utc': utc(), 'reason': reason}, indent=2) + '\n')
            except OSError as error:
                print('Não foi possível gravar interruption.json: ' + str(error), file=sys.stderr)
    def on_signal(number, frame):
        request_stop('Sinal externo recebido: ' + str(number))
    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        previous[number] = signal.signal(number, on_signal)
    try:
        with (reports / 'disk-usage.tsv').open('w') as log:
            writer = csv.writer(log, delimiter='\t')
            writer.writerow(['utc', 'used_bytes', 'available_bytes', 'used_percent'])
            while process.poll() is None:
                try:
                    snapshot = storage()
                    writer.writerow([snapshot['utc'], snapshot['used_bytes'], snapshot['available_bytes'],
                                     '{:.4f}'.format(100 * snapshot['used_fraction'])])
                    log.flush()
                    require_storage(snapshot)
                except (OSError, ValueError) as error:
                    request_stop('Monitor de disco: ' + str(error))
                try:
                    process.wait(timeout=interval)
                except subprocess.TimeoutExpired:
                    pass
            code = process.wait()
    except BaseException:
        request_stop('Falha/interrupção do monitor; não deixar execução sem monitoramento.')
        process.wait()
        raise
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
    print('Código de saída do Nextflow: ' + str(code), flush=True)
    (reports / 'nextflow-exit.json').write_text(json.dumps({
        'utc': utc(), 'nextflow_exit': code, 'interruption': interrupted}, indent=2) + '\n')
    return 88 if interrupted else (code if code >= 0 else 128 - code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--run', action='store_true')
    group.add_argument('--check-paths', action='store_true')
    group.add_argument('--stage-guard')
    parser.add_argument('--reports', type=Path)
    args = parser.parse_args()
    if args.check_paths:
        check_paths()
        return 0
    if args.stage_guard is not None:
        stage_guard(() if args.stage_guard == 'none' else tuple(args.stage_guard.split(',')))
        return 0
    if args.check:
        with tempfile.TemporaryDirectory(prefix='brisance-full-preflight-') as folder:
            preflight(Path(folder))
        print('CHECAGEM OK. Nenhuma trimagem, alinhamento ou chamada iniciada.')
        return 0
    reports = args.reports
    if (not reports or reports.parent != ROOT / 'reports' / DATASET or
            not re.fullmatch(r'execution-[A-Za-z0-9]{6}', reports.name)):
        raise ValueError('Diretório de relatórios inesperado; use o launcher .sh.')
    no_symlink(reports)
    if not reports.is_dir() or not os.environ.get('STY'):
        raise ValueError('É necessário executar o launcher dentro da screen.')
    report = preflight(reports)
    (reports / 'preflight.json').write_text(json.dumps(report, indent=2) + '\n')
    archive_inputs(reports)
    # Fail closed if inputs or capacity changed during preflight/archiving.
    if raw_metadata() != report['raw']:
        raise ValueError('Os metadados dos FASTQs mudaram durante a checagem.')
    require_storage(storage())
    check_paths()
    command = nf_command('finalize', reports / 'nextflow.log', ROOT / 'work' / DATASET,
                         reports / 'launcher-safety.config', reports)
    (reports / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
    started = utc()
    print('Início UTC do Nextflow integrado: ' + started, flush=True)
    print('Fluxo de 100%: FASTQs originais → trimagem/FastQC → alinhamento/BQSR → chamada → filtros → VEP → TLOD positivo.', flush=True)
    code = monitor(command, reports)
    (reports / 'timing.json').write_text(json.dumps({'start_utc': started, 'end_utc': utc(), 'launcher_exit': code}, indent=2) + '\n')
    return code


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('ERRO: ' + str(error), file=sys.stderr)
        print('Nada será apagado ou reiniciado automaticamente. Revise o log antes de retomar.', file=sys.stderr)
        sys.exit(1)
