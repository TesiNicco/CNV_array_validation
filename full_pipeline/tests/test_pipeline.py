"""Synthetic contract tests; no patient data, installations or model execution."""
import copy
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import yaml

PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE / 'bin'))
from common import load_config, read_manifest, run
from prepare_inputs import prepare_batch
from prepare_cnvalidatron import prepare_validation
from run_validation import validate_batch


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cnv-contract-')
        self.root = Path(self.temp.name)
        self.cfg = yaml.safe_load((PIPELINE / 'config/config.example.yaml').read_text())
        self.cfg['batches']['batch_A']['qc_bim'] = None
        self.cfg['tools']['validation_script'] = str(PIPELINE.parent / 'cnvalidatron_wrapper/bin/validation_CNV.r')
        self.cfg['tools']['penncnv_dir'] = str(self.root / 'PennCNV')

    def tearDown(self):
        self.temp.cleanup()

    def signal(self, name, positions=(200, 100, 100), baf=0.5):
        path = self.root / name
        pd.DataFrame({'Name': ['rs' + str(p) for p in positions],
                      'Chr': ['chr1'] * len(positions), 'Position': positions,
                      'original.GType': ['AB'] * len(positions),
                      'original.Log R Ratio': [0.1] * len(positions),
                      'original.B Allele Freq': [baf] * len(positions)}).to_csv(
                          path, sep='\t', index=False)
        return path

    def batch(self, samples):
        root = self.root / 'batch'
        root.mkdir()
        return prepare_batch(self.cfg, 'batch_A', samples, root), root

    def test_filter_sort_deduplicate_and_preserve_manifest_id(self):
        signal = self.signal('unrelated-filename.txt')
        bim = self.root / 'qc.bim'
        bim.write_text('1 rs100 0 100 A G\n')
        self.cfg['batches']['batch_A']['qc_bim'] = str(bim)
        prepared, _ = self.batch([{'sample_id': '001', 'signal_file': str(signal)}])
        result = pd.read_csv(prepared[0]['signal_file'], sep='\t')
        self.assertEqual(result['Position'].tolist(), [100])
        self.assertEqual(Path(prepared[0]['signal_file']).name, '001.signal.tsv')
        self.assertIn('Log R Ratio', result)

    def test_probe_mismatch_fails_before_pfb(self):
        a, b = self.signal('a.tsv'), self.signal('b.tsv', (100,))
        with self.assertRaisesRegex(ValueError, 'filtered probes differ'):
            self.batch([{'sample_id': 'a', 'signal_file': str(a)},
                        {'sample_id': 'b', 'signal_file': str(b)}])

    def test_common_probes_and_minimum_count_are_explicit(self):
        self.cfg['batches']['batch_A'].update(common_snps_only=True, min_input_snps=2)
        paths = [self.signal('a.tsv', (100, 200)), self.signal('b.tsv', (100, 300)),
                 self.signal('c.tsv', (100,))]
        prepared, root = self.batch([{'sample_id': sid, 'signal_file': str(path)}
                                    for sid, path in zip(('a', 'b', 'c'), paths)])
        self.assertEqual([s['sample_id'] for s in prepared], ['a', 'b'])
        for sample in prepared:
            self.assertEqual(pd.read_csv(sample['signal_file'], sep='\t')['Position'].tolist(), [100])
        self.assertIn('below_min_input_snps', (root / 'sample_qc.tsv').read_text())

    def test_build_mismatches_are_rejected_without_liftover(self):
        for section, key in (('references', 'excluded_regions_genome_build'),
                             ('references', 'gc_genome_build'),
                             ('batches', 'qc_genome_build')):
            cfg = copy.deepcopy(self.cfg)
            if section == 'batches':
                cfg[section]['batch_A'][key] = 'hg38'
                cfg[section]['batch_A']['qc_bim'] = 'qc.bim'
            else:
                cfg[section][key] = 'hg38'
            path = self.root / 'config.yaml'
            path.write_text(yaml.safe_dump(cfg))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'must match'):
                load_config(path)

    def test_relative_manifest_paths_and_bad_id(self):
        manifest = self.root / 'samples.tsv'
        manifest.write_text('sample_id\tbatch\tsignal_file\n001\tbatch_A\tinput.txt\n')
        self.cfg['samples_manifest'] = str(manifest)
        rows = read_manifest(self.cfg)
        self.assertEqual(rows[0]['sample_id'], '001')
        self.assertEqual(rows[0]['signal_file'], str(self.root / 'input.txt'))
        manifest.write_text('sample_id\tbatch\tsignal_file\nbad_id\tbatch_A\tinput.txt\n')
        with self.assertRaisesRegex(ValueError, 'letters, digits'):
            read_manifest(self.cfg)

    def test_default_penncnv_uses_active_environment(self):
        self.cfg['tools']['penncnv_dir'] = None
        path = self.root / 'config.yaml'
        path.write_text(yaml.safe_dump(self.cfg))
        with patch.dict(os.environ, {'CONDA_PREFIX': str(self.root / 'env')}):
            cfg = load_config(path)
        self.assertEqual(cfg['tools']['penncnv_dir'], str(self.root / 'env/opt/PennCNV-1.0.5'))

    def test_default_penncnv_requires_environment_activation(self):
        self.cfg['tools']['penncnv_dir'] = None
        path = self.root / 'config.yaml'
        path.write_text(yaml.safe_dump(self.cfg))
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, 'Activate'):
            load_config(path)

    def validation_inputs(self):
        signal = self.signal('source.tsv', (100, 200))
        prepared, root = self.batch([{'sample_id': '001', 'signal_file': str(signal)}])
        pfb = root / 'probes.pfb'
        pfb.write_text('Name\tChr\tPosition\tPFB\nrs100\t1\t100\t0.5\nrs200\t1\t200\t0.5\n')
        cnv = root / 'calls.cnv'
        cnv.write_text(f'chr1:100-200 numsnp=2 length=101 state2,cn=1 {prepared[0]["signal_file"]}\n')
        return pfb, cnv, prepared, root

    def test_cnv_parsing_uses_explicit_manifest_identity(self):
        pfb, cnv, prepared, root = self.validation_inputs()
        with patch('prepare_cnvalidatron.run') as mocked:
            out = prepare_validation(pfb, cnv, prepared, root)
        calls = pd.read_csv(out / 'cnvs.tsv', sep='\t', dtype={'sample_ID': str})
        self.assertEqual(calls.iloc[0]['sample_ID'], '001')
        self.assertEqual(calls.iloc[0]['GT'], 1)
        self.assertEqual(calls.iloc[0]['CN'], 1)
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(pd.read_csv(out / 'signals/001.tsv', sep='\t')['Start'].tolist(), [100, 200])

    def test_worker_failure_propagates_instead_of_polling(self):
        pfb, cnv, prepared, root = self.validation_inputs()
        with patch('prepare_cnvalidatron.run'):
            out = prepare_validation(pfb, cnv, prepared, root)
        with patch('run_validation.run', side_effect=subprocess.CalledProcessError(7, 'Rscript')):
            with self.assertRaises(subprocess.CalledProcessError):
                validate_batch(self.cfg, out)
        self.assertFalse((out / 'results/final_predictions.tsv').exists())

    def test_empty_calls_write_header_without_worker(self):
        pfb, cnv, prepared, root = self.validation_inputs()
        cnv.write_text('')
        with patch('prepare_cnvalidatron.run'):
            out = prepare_validation(pfb, cnv, prepared, root)
        with patch('run_validation.run') as worker:
            validate_batch(self.cfg, out)
        worker.assert_not_called()
        self.assertTrue(pd.read_csv(out / 'results/final_predictions.tsv', sep='\t').empty)

    def test_process_exit_code_is_checked(self):
        with self.assertRaises(subprocess.CalledProcessError):
            run([sys.executable, '-c', 'raise SystemExit(7)'], self.root / 'process.log')


if __name__ == '__main__':
    unittest.main()
