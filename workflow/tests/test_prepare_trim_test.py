"""Small synthetic fixtures exercise the prefix helper, not scientific accuracy."""

import csv
import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'prepare_trim_test.py'
SPEC = importlib.util.spec_from_file_location('prepare_trim_test', SCRIPT)
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


class PrefixTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='brisance-prefix-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = []
        for sample, role in [('somatico', 'tumor'), ('germinativo', 'normal')]:
            paths = []
            for mate in (1, 2):
                path = self.root / f'{role}_R{mate}.fastq.gz'
                records = ''.join(
                    f'@{role}:{number}/{mate}\nACGTACGT\n+\nIIIIIIII\n'
                    for number in range(8)
                )
                with gzip.open(path, 'wt', encoding='ascii') as stream:
                    stream.write(records)
                paths.append(str(path))
            self.rows.append(dict(sample=sample, role=role, pair_id=role,
                                  fastq_1=paths[0], fastq_2=paths[1]))
        self.sheet = self.root / 'input.csv'
        with self.sheet.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=HELPER.COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows)

    def test_prefix_is_paired_and_originals_unchanged(self):
        before = {path: Path(path).read_bytes() for row in self.rows
                  for path in [row['fastq_1'], row['fastq_2']]}
        result = HELPER.prepare(self.sheet, self.root / 'output', 3)
        with result.open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        for row in rows:
            for key in ('fastq_1', 'fastq_2'):
                with gzip.open(row[key], 'rt') as stream:
                    self.assertEqual(len(stream.readlines()), 12)
        for path, contents in before.items():
            self.assertEqual(Path(path).read_bytes(), contents)

    def test_repeated_preparation_uses_new_directory(self):
        first = HELPER.prepare(self.sheet, self.root / 'output', 2)
        before = first.read_bytes()
        second = HELPER.prepare(self.sheet, self.root / 'output', 2)
        self.assertNotEqual(first.parent, second.parent)
        self.assertEqual(first.read_bytes(), before)

    def test_mismatched_mates_rejected(self):
        with gzip.open(self.rows[0]['fastq_2'], 'wt') as stream:
            stream.write('@different-id/2\nACGTACGT\n+\nIIIIIIII\n')
        with self.assertRaises(RuntimeError) as caught:
            HELPER.prepare(self.sheet, self.root / 'output', 1)
        self.assertIn('mate IDs differ', str(caught.exception.__cause__))
        self.assertFalse(list((self.root / 'output').glob('*/samplesheet.csv')))

    def test_short_input_rejected(self):
        with self.assertRaises(RuntimeError):
            HELPER.prepare(self.sheet, self.root / 'output', 9)
        self.assertFalse(list((self.root / 'output').glob('*/samplesheet.csv')))

    def test_read_count_bound(self):
        for count in (0, 1000001):
            with self.assertRaises(ValueError):
                HELPER.prepare(self.sheet, self.root / 'output', count)


if __name__ == '__main__':
    unittest.main()
