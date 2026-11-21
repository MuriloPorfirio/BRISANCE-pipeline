"""Optional somatic input validation and real Nextflow/fake-tool parameter wiring."""
import copy
import io
import itertools
import os
from pathlib import Path
import tarfile
import unittest
from unittest.mock import patch

import test_bam_pon_qc as bam_tests
import configure_brisance as cfg
import execute_analysis as execution
import run_from_file as fixed
import somatic_inputs as inputs
import check_environment as environment


def priors_file(path, sample='TUMOR', bad=False):
    columns = ['context', 'rev_comp'] + ['f1r2_' + b for b in 'acgt'] + ['f2r1_' + b for b in 'acgt'] + [
        'hom_ref', 'germline_het', 'somatic_het', 'hom_var', 'num_examples', 'num_alt_examples']
    text = '#<METADATA>SAMPLE=' + sample + '\n' + '\t'.join(columns) + '\n'
    for bases in itertools.product('ACGT', repeat=3):
        context = ''.join(bases)
        text += '\t'.join([context, context.translate(str.maketrans('ACGT', 'TGCA'))[::-1]] +
                          ['0'] * 8 + ['NaN' if bad else '1', '0', '0', '0', '0', '0']) + '\n'
    payload = text.encode()
    with tarfile.open(path, 'w:gz') as archive:
        member = tarfile.TarInfo(sample + '.orientation_priors')
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))


class SomaticModelsTests(unittest.TestCase):
    def setUp(self):
        bam_tests.BamPonQcTests.setUp(self)
        self.sites = self.fixture.base / 'common.vcf.gz'
        self.sites.write_text('SYNTHETIC; real resource checked inside workflow')
        Path(str(self.sites) + '.tbi').write_text('SYNTHETIC INDEX')
        self.priors = self.fixture.base / 'priors.tar.gz'
        priors_file(self.priors)
        self.table = self.fixture.base / 'contamination.table'
        self.table.write_text('sample\tcontamination\terror\nTUMOR\t0.001\t0.0001\n')
        self.segments = self.fixture.base / 'segments.table'
        self.segments.write_text('#<METADATA>SAMPLE=TUMOR\ncontig\tstart\tend\tminor_allele_fraction\nchr1\t1\t100\t0.5\n')

    def modes(self, orientation, contamination, segments=True):
        if orientation != 'off':
            self.config['orientation'] = {'mode': orientation}
            if orientation == 'provided':
                self.config['orientation']['priors'] = str(self.priors)
        if contamination != 'off':
            self.config['contamination'] = {'mode': contamination}
            if contamination == 'auto':
                self.config['contamination']['sites'] = str(self.sites)
            else:
                self.config['contamination']['table'] = str(self.table)
                if segments:
                    self.config['contamination']['segments'] = str(self.segments)

    def test_auto_and_provided_are_independent_and_have_correct_task_counts(self):
        for orientation, contamination, extra in [('auto', 'off', 1), ('off', 'auto', 4),
                                                 ('auto', 'auto', 5), ('provided', 'provided', 0)]:
            with self.subTest(orientation=orientation, contamination=contamination):
                self.config.pop('orientation', None)
                self.config.pop('contamination', None)
                self.modes(orientation, contamination)
                checked = cfg.validate_configuration(self.config)
                self.assertEqual(execution.expected_tasks(checked), 9 + extra)

    def test_reject_missing_mixed_or_stale_options(self):
        bad_options = [('orientation', {'mode': 'auto', 'priors': str(self.priors)}),
                       ('orientation', {'mode': 'provided'}), ('orientation', {'mode': 'off'}),
                       ('contamination', {'mode': 'auto'}),
                       ('contamination', {'mode': 'provided', 'sites': str(self.sites), 'table': str(self.table)})]
        for key, value in bad_options:
            with self.subTest(value=value):
                bad = copy.deepcopy(self.config)
                bad[key] = value
                with self.assertRaises(ValueError):
                    cfg.validate_configuration(bad)

    def test_wrong_sample_tables_and_priors_fail(self):
        self.modes('provided', 'provided')
        for path in (self.table, self.segments):
            original = path.read_text()
            path.write_text(original.replace('TUMOR', 'OTHER'))
            with self.assertRaises(ValueError):
                cfg.validate_configuration(self.config)
            path.write_text(original)
        priors_file(self.priors, sample='OTHER')
        with self.assertRaises(ValueError):
            cfg.validate_configuration(self.config)

    def test_malformed_fractions_coordinates_and_empty_segments_fail(self):
        for fraction in ('NaN', 'Infinity', '-0.1', '1.1'):
            self.table.write_text('sample\tcontamination\terror\nTUMOR\t' + fraction + '\t0\n')
            with self.assertRaises(ValueError):
                inputs.check_contamination(self.table, 'TUMOR')
        for body in ('', 'chr2\t1\t100\t0.5\n', 'chr1\t1\t101\t0.5\n', 'chr1\t50\t10\t0.5\n',
                     'chr1\t1\t60\t0.5\nchr1\t60\t100\t0.5\n'):
            self.segments.write_text('#<METADATA>SAMPLE=TUMOR\ncontig\tstart\tend\tminor_allele_fraction\n' + body)
            with self.assertRaises(ValueError):
                inputs.check_segments(self.segments, 'TUMOR', self.fixture.fasta)
        priors_file(self.priors, bad=True)
        with self.assertRaises(ValueError):
            inputs.check_priors(self.priors, 'TUMOR')

    def test_unsafe_tar_is_never_extracted(self):
        with tarfile.open(self.priors, 'w:gz') as archive:
            member = tarfile.TarInfo('../outside.orientation_priors')
            member.size = 1
            archive.addfile(member, io.BytesIO(b'x'))
        with self.assertRaises(ValueError):
            inputs.check_priors(self.priors, 'TUMOR')

    def test_ini_modes_and_disabled_defaults(self):
        from test_fixed_settings import render
        legacy = render(self.fixture.config)
        raw, _ = fixed.parse_settings('test.ini', content=legacy + '\n[orientation]\nmode=off\n[contamination]\nmode=off\n')
        baseline, _ = fixed.parse_settings('test.ini', content=legacy)
        self.assertEqual(raw, baseline)
        raw, _ = fixed.parse_settings('test.ini', content=legacy + '\n[orientation]\nmode=auto\n[contamination]\nmode=auto\nsites=' + str(self.sites))
        checked = cfg.validate_configuration(raw)
        self.assertEqual(checked['orientation'], {'mode': 'auto'})
        self.assertEqual(checked['contamination']['sites'], str(self.sites))
        with self.assertRaises(ValueError):
            fixed.parse_settings('test.ini', content=legacy + '\n[orientation]\nmode=off\npriors=' + str(self.priors))

    def test_shipped_ini_examples_can_enable_both_models(self):
        from configparser import ConfigParser

        for name in ('brisance.example.ini', 'brisance.bam.example.ini'):
            with self.subTest(template=name):
                path = Path(fixed.__file__).parent / name
                settings = ConfigParser(interpolation=None)
                settings.read(path)
                for section in ('orientation', 'contamination'):
                    self.assertEqual(settings[section]['mode'], 'off')
                    settings[section]['mode'] = 'auto'
                settings['contamination']['sites'] = str(self.sites)
                edited = io.StringIO()
                settings.write(edited)
                raw, _ = fixed.parse_settings(path, content=edited.getvalue())
                self.assertEqual(raw['orientation'], {'mode': 'auto'})
                self.assertEqual(raw['contamination'], {'mode': 'auto', 'sites': str(self.sites)})

    def test_missing_requested_tool_capability_blocks_preflight(self):
        self.modes('auto', 'auto')
        checker = environment.EnvironmentCheck.__new__(environment.EnvironmentCheck)
        checker.config = self.config
        checker.images = {spec['image']: 'sha256:' + 'a' * 64 for spec in environment.IMAGES}
        with patch.object(checker, 'container_command', return_value=['simulated-help']), \
                patch.object(checker, 'run_command', return_value='No supported flags'):
            with self.assertRaisesRegex(environment.CheckFailure, 'lacks requested options'):
                checker.check_somatic_capabilities()

    def graph(self, orientation, contamination, segments=True, fastq=False):
        if fastq:
            self.config = copy.deepcopy(self.fixture.config)
        self.modes(orientation, contamination, segments)
        calls = bam_tests.BamPonQcTests.graph(self, pon=True, prepared=True, qc=True)
        commands = [row['args'] for row in calls if row['tool'] == 'gatk' and '--version' not in row['args']]
        filtering = next(args for args in commands if 'FilterMutectCalls' in args)
        self.assertEqual('--orientation-bias-artifact-priors' in filtering, orientation != 'off')
        self.assertEqual('--contamination-table' in filtering, contamination != 'off')
        self.assertEqual('--tumor-segmentation' in filtering, contamination == 'auto' or contamination == 'provided' and segments)
        self.assertEqual(sum('GetPileupSummaries' in args for args in commands), 2 if contamination == 'auto' else 0)
        self.assertEqual(sum('LearnReadOrientationModel' in args for args in commands), int(orientation == 'auto'))
        caller = next(row['args'] for row in calls if row['tool'] == 'pbrun' and row['args'][0] == 'mutectcaller' and '--version' not in row['args'])
        self.assertEqual('--mutect-f1r2-tar-gz' in caller, orientation == 'auto')

    @unittest.skipUnless(os.environ.get('BRISANCE_NEXTFLOW_TEST'), 'Optional real Nextflow / fake tools test.')
    def test_graph_both_auto(self):
        self.graph('auto', 'auto')

    @unittest.skipUnless(os.environ.get('BRISANCE_NEXTFLOW_TEST'), 'Optional real Nextflow / fake tools test.')
    def test_graph_orientation_only(self):
        self.graph('auto', 'off')

    @unittest.skipUnless(os.environ.get('BRISANCE_NEXTFLOW_TEST'), 'Optional real Nextflow / fake tools test.')
    def test_graph_contamination_only(self):
        self.graph('off', 'auto')

    @unittest.skipUnless(os.environ.get('BRISANCE_NEXTFLOW_TEST'), 'Optional real Nextflow / fake tools test.')
    def test_graph_provided(self):
        self.graph('provided', 'provided')

    @unittest.skipUnless(os.environ.get('BRISANCE_NEXTFLOW_TEST'), 'Optional real Nextflow / fake tools test.')
    def test_graph_provided_contamination_without_segments(self):
        self.graph('off', 'provided', segments=False)

    @unittest.skipUnless(os.environ.get('BRISANCE_NEXTFLOW_TEST'), 'Optional real Nextflow / fake tools test.')
    def test_graph_fastq_both_auto(self):
        self.graph('auto', 'auto', fastq=True)

    @unittest.skipUnless(os.environ.get('BRISANCE_NEXTFLOW_TEST'), 'Optional real Nextflow / fake tools test.')
    def test_graph_missing_F1R2_never_silently_disables_orientation(self):
        with patch.dict(os.environ, {'BRISANCE_TEST_OMIT_F1R2': '1'}):
            with self.assertRaisesRegex(AssertionError, 'Requested orientation model produced no F1R2/priors'):
                self.graph('auto', 'auto')
        import json
        calls = [json.loads(line) for line in (self.fixture.base / 'calls.jsonl').read_text().splitlines()]
        self.assertFalse(any(row['tool'] == 'gatk' and 'FilterMutectCalls' in row['args'] for row in calls))
