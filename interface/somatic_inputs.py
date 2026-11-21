"""Validate optional GATK 4.6.2.0 per-sample filtering inputs without extracting archives."""
import csv
import itertools
import math
from pathlib import Path, PurePosixPath
import tarfile


def table(text):
    metadata, lines = {}, []
    for line in text.splitlines():
        if line.startswith('#<METADATA>'):
            key, separator, value = line[len('#<METADATA>'):].partition('=')
            if not separator or key in metadata:
                raise ValueError('Missing/repeated GATK table metadata.')
            metadata[key] = value
        elif line.strip() and not line.startswith('#'):
            lines.append(line)
    reader = csv.DictReader(lines, delimiter='\t')
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError('Missing/duplicate GATK table columns.')
    rows = list(reader)
    if any(None in row or None in row.values() for row in rows):
        raise ValueError('Malformed GATK table row.')
    return metadata, set(reader.fieldnames), rows


def fraction(value, label):
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError('Invalid finite fraction: ' + label)
    return number


def small_text(path):
    if Path(path).stat().st_size > 16 * 1024 ** 2:
        raise ValueError('Unexpectedly large per-sample table: ' + str(path))
    return Path(path).read_text()


def check_contamination(path, sample):
    _, columns, rows = table(small_text(path))
    if not {'sample', 'contamination', 'error'} <= columns or len(rows) != 1 or rows[0]['sample'] != sample:
        raise ValueError('Contamination table must contain exactly the configured tumor sample: ' + sample)
    return {name: fraction(rows[0][name], name) for name in ('contamination', 'error')}


def check_segments(path, sample, fasta):
    metadata, columns, rows = table(small_text(path))
    if metadata.get('SAMPLE') != sample or not {'contig', 'start', 'end', 'minor_allele_fraction'} <= columns or not rows:
        raise ValueError('Segmentation requires GATK SAMPLE metadata and nonempty tumor segments: ' + sample)
    lengths = {parts[0]: int(parts[1]) for line in Path(str(fasta) + '.fai').read_text().splitlines()
               if (parts := line.split('\t'))}
    previous = {}
    for row in rows:
        chrom, start, end = row['contig'], int(row['start']), int(row['end'])
        if chrom not in lengths or not 1 <= start <= end <= lengths[chrom] or start <= previous.get(chrom, 0):
            raise ValueError('Segmentation contig/bounds/order incompatible with FASTA.')
        previous[chrom] = end
        fraction(row['minor_allele_fraction'], 'minor_allele_fraction')
    return {'segments': len(rows), 'sample': sample}


def check_priors(path, sample):
    samples = set()
    contexts = {''.join(bases) for bases in itertools.product('ACGT', repeat=3)}
    probability_columns = ['f1r2_' + base for base in 'acgt'] + ['f2r1_' + base for base in 'acgt'] + [
        'hom_ref', 'germline_het', 'somatic_het', 'hom_var']
    total = 0
    with tarfile.open(path, 'r:gz') as archive:
        for index, member in enumerate(archive):
            name = PurePosixPath(member.name)
            if index > 32 or name.is_absolute() or '..' in name.parts or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe/unexpected orientation-priors archive member.')
            if member.isdir():
                continue
            total += member.size
            if not member.name.endswith('.orientation_priors') or total > 16 * 1024 ** 2:
                raise ValueError('Expected GATK .orientation_priors tables, not F1R2 counts.')
            metadata, columns, rows = table(archive.extractfile(member).read().decode())
            current = metadata.get('SAMPLE')
            if not current or current in samples or not set(probability_columns + ['context', 'rev_comp', 'num_examples', 'num_alt_examples']) <= columns:
                raise ValueError('Orientation-priors table has missing/duplicate sample or columns.')
            samples.add(current)
            if len(rows) != 64 or {row['context'] for row in rows} != contexts:
                raise ValueError('Orientation priors must contain the 64 distinct trinucleotide contexts.')
            for row in rows:
                if row['rev_comp'] != row['context'].translate(str.maketrans('ACGT', 'TGCA'))[::-1]:
                    raise ValueError('Invalid reverse-complement context in priors.')
                if abs(sum(fraction(row[column], column) for column in probability_columns) - 1) > .001:
                    raise ValueError('Orientation-prior probabilities do not sum to one.')
                if not 0 <= int(row['num_alt_examples']) <= int(row['num_examples']):
                    raise ValueError('Invalid orientation-prior example counts.')
    if sample not in samples:
        raise ValueError('Orientation priors do not contain configured tumor sample: ' + sample)
    return {'samples': sorted(samples), 'tumor_sample': sample}


def input_files(config):
    files = []
    for key, names in (('orientation', ('priors',)), ('contamination', ('sites', 'table', 'segments'))):
        for name in names:
            if config.get(key, {}).get(name):
                path = Path(config[key][name])
                files.append(path)
                if name == 'sites':
                    files.append(Path(str(path) + '.tbi'))
    return files


def validate_options(config, readable_file, fasta):
    result = {}
    tumor = next(row['sample'] for row in config['samples'] if row['role'] == 'tumor')
    for name in ('orientation', 'contamination'):
        if name not in config:
            continue
        options = config[name]
        if not isinstance(options, dict) or options.get('mode') not in ('auto', 'provided'):
            raise ValueError(name + ' requires mode auto/provided; omit disabled options.')
        mode = options['mode']
        required = {'mode'}
        allowed = set(required)
        if name == 'orientation' and mode == 'provided':
            required.add('priors')
            allowed.add('priors')
        elif name == 'contamination':
            required.add('sites' if mode == 'auto' else 'table')
            allowed = required | ({'segments'} if mode == 'provided' else set())
        if not required <= set(options) <= allowed:
            raise ValueError(name + ': required inputs ' + str(sorted(required)) + '; optional inputs ' + str(sorted(allowed - required)))
        checked = {'mode': mode}
        for key in set(options) - {'mode'}:
            suffix = ('.tar.gz',) if key == 'priors' else (('.vcf.gz',) if key == 'sites' else None)
            checked[key] = str(readable_file(options[key], suffix))
            if key == 'sites':
                readable_file(checked[key] + '.tbi')
        if 'priors' in checked:
            check_priors(checked['priors'], tumor)
        if 'table' in checked:
            check_contamination(checked['table'], tumor)
        if 'segments' in checked:
            check_segments(checked['segments'], tumor, fasta)
        result[name] = checked
    return result
