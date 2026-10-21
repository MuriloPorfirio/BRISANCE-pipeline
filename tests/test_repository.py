"""Repository packaging/recipe tests. Synthetic inputs only; no Docker/GPU/WGS."""
import csv
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / 'historical_workflows/parabricks/hg008_commands.py'


def load_recipe():
    spec = importlib.util.spec_from_file_location('hg008_recipe', RECIPE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackagingTests(unittest.TestCase):
    def test_scientific_workflow_matches_preserved_manifest(self):
        data = json.loads((ROOT / 'provenance/workflow_manifest.json').read_text())
        self.assertEqual(len(data['files']), 13)
        for record in data['files']:
            self.assertEqual(hashlib.sha256((ROOT / record['path']).read_bytes()).hexdigest(), record['sha256'], record['path'])

    def test_source_snapshots_match_original_hashes_and_git_blobs(self):
        data = json.loads((ROOT / 'provenance/source_manifest.json').read_text())
        self.assertEqual(len(data['files']), 31)
        for record in data['files']:
            payload = (ROOT / record['path']).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), record['sha256'], record['path'])
            git_blob = b'blob ' + str(len(payload)).encode() + b'\0' + payload
            self.assertEqual(hashlib.sha1(git_blob).hexdigest(), record['git_blob'], record['path'])

    def test_four_source_commits_are_recorded(self):
        sources = json.loads((ROOT / 'provenance/source_repositories.json').read_text())['repositories']
        self.assertEqual(len(sources), 4)
        for source in sources:
            self.assertRegex(source['commit'], r'^[0-9a-f]{40}$')
            self.assertTrue((ROOT / source['snapshot']).is_dir())

    def test_input_sizes_and_pair_counts(self):
        with (ROOT / 'validation/hg008_100pct/input_files.csv').open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 10)
        self.assertEqual(sum(int(row['compressed_bytes']) for row in rows), 500242287130)
        self.assertEqual(sum(row['role'] == 'tumor' for row in rows), 8)
        self.assertEqual(sum(row['role'] == 'normal' for row in rows), 2)

    def test_transcribed_trace_scope_and_sums(self):
        with (ROOT / 'validation/hg008_100pct/tasks_transcribed.csv').open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 18)
        self.assertEqual(len({row['task_id'] for row in rows}), 18)
        self.assertTrue(all(row['status'] == 'COMPLETED' and row['exit'] == '0' for row in rows))
        total = lambda names: sum((Decimal(row['realtime_seconds']) for row in rows if row['task_name'] in names), Decimal(0))
        self.assertEqual(total({'FQ2BAM', 'MUTECT_CALLER'}), 15140)
        self.assertEqual(total({'FQ2BAM', 'APPLY_BQSR', 'MUTECT_CALLER'}), 22407)
        self.assertEqual(total({'TRIM_GALORE'}), 295269)

    def test_public_hg008_evaluation_describes_full_inputs_only(self):
        for name in ('README.md', 'validation/README.md', 'workflow/README.md',
                     'analysis/runtime/README.md', 'pipeline/README.md',
                     'docs/hg008-reproduction.md', 'docs/outputs.md'):
            text = (ROOT / name).read_text()
            self.assertNotRegex(text, r'20%|20pct|16,917|16917|interface_hg008_small|small prefix')
        record = (ROOT / 'validation/hg008_100pct/README.md').read_text()
        self.assertIn('500,242,287,130', record)
        self.assertIn('17,455', record)
        self.assertIn('no subsampling', record)
        for name in ('validation/interface_hg008_small', 'workflow/prepare_trim_test.py',
                     'workflow/prepare_fraction_test.py', 'workflow/run_hg008_20pct.sh'):
            self.assertFalse((ROOT / name).exists(), name)

    def test_example_sheet_has_placeholders_and_all_pairs(self):
        with (ROOT / 'assets/hg008_samplesheet.example.csv').open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 5)
        self.assertEqual(len({row['pair_id'] for row in rows}), 5)
        for row in rows:
            for column in ('fastq_1', 'fastq_2'):
                self.assertTrue(row[column].startswith('/path/to/HG008_'))

    def test_reference_hash_syntax(self):
        with (ROOT / 'validation/reference_checksums.tsv').open() as handle:
            rows = list(csv.DictReader(handle, delimiter='\t'))
        self.assertEqual(len(rows), 12)
        for row in rows:
            self.assertRegex(row['sha256'], r'^[0-9a-f]{64}$', row['resource'])

    def test_current_documentation_local_links_resolve(self):
        for document in ROOT.rglob('*.md'):
            if any(part in document.parts for part in ('source_snapshots', '.git', '.brisance')):
                continue
            for target in re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', document.read_text()):
                if '://' in target or target.startswith(('mailto:', '#')):
                    continue
                target = unquote(target.split('#', 1)[0])
                self.assertTrue((document.parent / target).exists(), '{} -> {}'.format(document.relative_to(ROOT), target))

    def test_no_scientific_payloads_or_credentials_in_package(self):
        forbidden = ('.fastq', '.fastq.gz', '.fq', '.fq.gz', '.bam', '.bai', '.cram', '.vcf', '.vcf.gz', '.fasta', '.fa', '.pem', '.key')
        for path in ROOT.rglob('*'):
            if not path.is_file() or any(part in path.parts for part in ('.git', '__pycache__', '.brisance')):
                continue
            self.assertFalse(path.name.endswith(forbidden), str(path))
            self.assertLess(path.stat().st_size, 2_000_000, str(path))
            text = path.read_text(encoding='utf-8')
            self.assertIsNone(re.search(r'(?:ghp_|github_pat_)[A-Za-z0-9_]{30,}', text), str(path))

    def test_license_and_no_citation_request_before_publication(self):
        self.assertIn('Non-Commercial', (ROOT / 'LICENSE').read_text())
        self.assertFalse((ROOT / 'CITATION.cff').exists())
        readme = (ROOT / 'README.md').read_text()
        self.assertNotIn('CITATION.cff', readme)
        self.assertNotRegex(readme.lower(), r'how to cite|cite this|citation information|preprint coming')

    def test_project_acknowledgement_and_manuscript_author_order(self):
        readme = (ROOT / 'README.md').read_text()
        self.assertIn('InovaCriança', readme)
        self.assertIn('444217/2023-1', readme)
        self.assertIn('Brazilian Ministry of Health and CNPq', readme)
        authors = ['Murilo Porfírio de Aguiar', 'Saloe Bispo', 'Silvia Aparecida Teixeira',
                   'Rui Manuel Reis', 'Luciane Sussuchi da Silva', 'Letícia Graziela Costa Santos']
        positions = [readme.index(author) for author in authors]
        self.assertEqual(positions, sorted(positions))

    def test_active_shell_files_parse(self):
        files = list((ROOT / 'workflow').glob('*.sh'))
        files += list((ROOT / 'analysis/variant_comparison').glob('*.sh'))
        files += [ROOT / 'setup_brisance.sh', ROOT / 'interface/run_brisance.sh']
        for path in files:
            result = subprocess.run(['bash', '-n', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, str(path) + result.stderr)


class HistoricalRecipeTests(unittest.TestCase):
    def setUp(self):
        self.module = load_recipe()

    def render(self, stage):
        return self.module.recipe('/example/hg008', '/example/cache', stage)

    def test_cli_only_prints_and_does_not_create_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / 'does-not-exist'
            result = subprocess.run([sys.executable, '-B', str(RECIPE), '--base', str(base),
                                     '--cache', '/example/cache', '--stage', 'all'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(base.exists())
            self.assertIn('RECONSTRUCTED RECIPE', result.stdout)

    def test_all_generated_shell_syntax_is_valid(self):
        for stage in (*self.module.STAGES, 'all'):
            result = subprocess.run(['bash', '-n'], input=self.render(stage), capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, stage + result.stderr)

    def test_actual_hg008_alignment_inputs_and_historical_options(self):
        tumor, normal = self.render('align-tumor'), self.render('align-normal')
        self.assertEqual(tumor.count('--in-fq'), 4)
        self.assertEqual(normal.count('--in-fq'), 1)
        self.assertIn('somatico-tentativa2', tumor)
        self.assertIn(self.module.NORMAL, normal)
        self.assertEqual(tumor.count('--knownSites'), 3)
        self.assertIn('--tmp-dir', tumor)
        self.assertNotIn('--tmp-dir', normal)
        self.assertNotIn('--bwa-cpu-thread-pool', tumor)
        self.assertNotIn('--num-gpus', tumor)
        self.assertNotIn('--memory-limit', tumor)

    def test_caller_not_replaced_with_generic_or_nextflow_command(self):
        call = self.render('call')
        self.assertIn('--num-htvc-threads 32', call)
        self.assertIn('--tumor-name somatico', call)
        self.assertIn('--normal-name germinativo', call)
        self.assertNotIn('--in-tumor-recal-file', call)
        self.assertNotIn('SRR789', call)
        self.assertNotIn('--num-gpus', call)

    def test_annotation_and_selection_use_observed_versions_and_expression(self):
        annotate = self.render('annotate')
        self.assertIn('release_113.0', annotate)
        self.assertIn('--cache_version 113', annotate)
        self.assertIn('--offline', annotate)
        self.assertIn('--fork 8', annotate)
        self.assertNotIn(':latest', annotate)
        self.assertIn('INFO/TLOD>0 && INFO/TLOD!="."', self.render('tlod'))

    def test_reheader_only_changes_sm_and_uses_index_eight(self):
        rg = self.render('read-groups')
        self.assertIn('reheader', rg)
        self.assertIn('SM:somatico', rg)
        self.assertIn('SM:germinativo', rg)
        self.assertIn('index -@ 8', rg)
        self.assertNotIn('addreplacerg', rg)
        self.assertNotIn('PL:ILLUMINA', rg)

    def test_relative_paths_and_invalid_gpu_are_rejected(self):
        with self.assertRaises(ValueError):
            self.module.recipe('relative', '/cache', 'call')
        with self.assertRaises(ValueError):
            self.module.recipe('/base', '/cache', 'call', tumor_gpu=-1)


class VariantComparisonTests(unittest.TestCase):
    def test_reconstructed_indel_step_refuses_reused_output(self):
        spec = importlib.util.spec_from_file_location('reconstructed_indels', ROOT / 'analysis/variant_comparison/05_compare_indels.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'indels.tsv'
            source.write_text('CHROM\tPOS\tREF\tALT\tTYPE\tINDEL_SUBTYPE\nchr1\t1\tA\tAT\tINDEL\tINS\n')
            existing = root / 'existing'
            existing.mkdir()
            with self.assertRaises(FileExistsError):
                module.compare(source, source, existing)

    def test_preserved_python_pipeline_on_small_synthetic_vcfs(self):
        scripts = ROOT / 'analysis/variant_comparison'
        header = '##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls, baseline = root / 'calls.vcf', root / 'baseline.vcf'
            calls.write_text(header + 'chr1\t1\t.\tA\tC\t.\tPASS\t.\nchr1\t2\t.\tA\tAT\t.\tPASS\t.\nchr1\t3\t.\tAT\tGC\t.\tPASS\t.\nchr1\t4\t.\tG\tA,T\t.\tPASS\t.\n')
            baseline.write_text(header + 'chr1\t1\t.\tA\tC\t.\tPASS\t.\nchr1\t2\t.\tA\tAT\t.\tPASS\t.\nchr1\t5\t.\tG\tC\t.\tPASS\t.\n')
            commands = [
                ['03_extract_variant_sets.py', calls, baseline, root / 'sets'],
                ['04_compare_snvs.py', root / 'sets/clara/snvs.tsv', root / 'sets/dragen/snvs.tsv', root / 'snvs'],
                ['05_compare_indels.py', root / 'sets/clara/indels.tsv', root / 'sets/dragen/indels.tsv', root / 'indels'],
                ['06_build_summary_table.py', root / 'snvs/summary.txt', root / 'indels/summary.txt', root / 'table'],
            ]
            for name, *args in commands:
                result = subprocess.run([sys.executable, '-B', str(scripts / name), *map(str, args)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with (root / 'table/manuscript_table.tsv').open() as handle:
                rows = list(csv.DictReader(handle, delimiter='\t'))
            total = rows[-1]
            self.assertEqual(total['Parabricks_total'], '4')
            self.assertEqual(total['DRAGEN_total'], '3')
            self.assertEqual(total['Shared'], '2')
            self.assertEqual(total['Shared_pct'], '40.00')


if __name__ == '__main__':
    unittest.main()
