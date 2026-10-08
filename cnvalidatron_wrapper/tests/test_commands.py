"""Exercise the real R commands; model inference is tested separately on the example."""
import csv
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / 'bin'
RSCRIPT = shutil.which('Rscript')
TOOLS_AVAILABLE = RSCRIPT and shutil.which('bgzip') and shutil.which('tabix')


def write_tsv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t', lineterminator='\n')
        writer.writerow(header)
        writer.writerows(rows)


def read_tsv(path):
    with path.open() as handle:
        return list(csv.DictReader(handle, delimiter='\t'))


@unittest.skipUnless(TOOLS_AVAILABLE, 'Activate the shared R/bgzip/tabix environment')
class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='wrapper-cli-')
        self.root = Path(self.temporary.name)
        self.ids = ['001', '002', 'control']
        for sid in self.ids:
            write_tsv(self.root / f'signals/{sid}.tsv',
                      ['Chr', 'Position', f'{sid}.Log R Ratio', f'{sid}.B Allele Freq', 'Log R Ratio Adjusted'],
                      [['chr22', pos, -0.1, 0.5, -0.25] for pos in [600, 500, 400, 300, 200, 100]])
        write_tsv(self.root / 'samples.tsv', ['sample_ID', 'file_path'],
                  [[sid, f'signals/{sid}.tsv'] for sid in self.ids])
        write_tsv(self.root / 'snps.tsv', ['Index', 'Name', 'Chr', 'Position'],
                  [[i, f'probe{i}', 22, pos] for i, pos in enumerate(range(100, 601, 100))])
        self.cnv_header = ['sample_ID', 'chr', 'start', 'end', 'GT', 'CN', 'numsnp']
        write_tsv(self.root / 'cnvs.tsv', self.cnv_header,
                  [['001', 22, 100, 300, 1, 1, 3], ['002', 22, 400, 600, 2, 3, 3]])
        self.model = self.root / 'model.rds'
        self.model.write_text('stub model; no model inference in these unit tests')
        self.worker = self.root / 'worker.R'
        self.worker.write_text('''
suppressPackageStartupMessages(library(data.table))
a <- commandArgs(trailingOnly = TRUE)
value <- function(flag) a[match(flag, a) + 1]
samples <- fread(value('--samples'), colClasses = list(character = 'sample_ID'))
cnvs <- fread(value('--cnvs'), colClasses = list(character = 'sample_ID'))
result <- cnvs[sample_ID %in% samples$sample_ID]
result[, pred := ifelse(GT == 1, 2L, 3L)]
fwrite(result, file.path(value('--outdir'), 'predictions.txt'), sep = '\\t')
''')

    def tearDown(self):
        self.temporary.cleanup()

    def run_command(self, script, arguments, env=None):
        return subprocess.run([RSCRIPT, '--vanilla', str(BIN / script), *map(str, arguments)],
                              cwd='/', env=env, capture_output=True, text=True, timeout=45)

    def prepare(self, output=None, cnv_format='table', extra=(), env=None):
        output = output or self.root / 'prepared'
        result = self.run_command('preparation.R', [
            '--samples', self.root / 'samples.tsv', '--snps', self.root / 'snps.tsv',
            '--cnvs', self.root / ('raw.cnv' if cnv_format == 'penncnv' else 'cnvs.tsv'),
            '--cnv-format', cnv_format, '--outdir', output, *extra], env=env)
        return result, output

    def launch(self, prepared, output=None, extra=(), worker=None):
        return self.run_command('parallelize_validation.r', [
            '--samples', prepared / 'samples.tsv', '--snps', prepared / 'snps.tsv',
            '--cnvs', prepared / 'cnvs.tsv', '--model', self.model,
            '--outdir', output or self.root / 'predictions', '--workers', '10',
            '--worker-script', worker or self.worker, *extra])

    def test_preparation_preserves_ids_adjusted_lrr_and_index_queries(self):
        result, output = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        samples = read_tsv(output / 'samples.tsv')
        self.assertEqual([r['sample_ID'] for r in samples], self.ids)
        signal = read_tsv(Path(samples[0]['file_path']))
        self.assertEqual([int(r['Start']) for r in signal], list(range(100, 601, 100)))
        self.assertTrue(all(float(r['Log R Ratio Adjusted']) == -0.25 for r in signal))
        self.assertTrue(all(float(r['Log R Ratio']) == -0.1 for r in signal))
        query = subprocess.run(['tabix', samples[0]['file_path_tabix'], '22:100-300'],
                               capture_output=True, text=True, check=True)
        self.assertEqual(len(query.stdout.splitlines()), 3)
        self.assertNotIn('Index', (output / 'snps.tsv').read_text().splitlines()[0])

    def test_distributed_raw_example_matches_after_preparation_references(self):
        examples = BIN.parent / 'example_data'
        before = examples / 'before_preparation'
        after = examples / 'after_preparation'
        output = self.root / 'distributed'
        result = self.run_command('preparation.R', [
            '--samples', before / 'samples.txt', '--snps', before / 'snps.txt',
            '--cnvs', before / 'cnvs.txt', '--cnv-format', 'penncnv', '--outdir', output])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_tsv(output / 'snps.tsv'), read_tsv(after / 'snps_ready.txt'))
        self.assertEqual(read_tsv(output / 'cnvs.tsv'), read_tsv(after / 'cnvs_ready.txt'))
        samples = read_tsv(output / 'samples.tsv')
        expected = read_tsv(after / 'samples_ready.txt')
        self.assertEqual([r['sample_ID'] for r in samples], [r['sample_ID'] for r in expected])
        for row, reference in zip(samples, expected):
            self.assertEqual(Path(row['file_path']).name, Path(reference['file_path']).name)
            self.assertEqual(Path(row['file_path_tabix']).name, Path(reference['file_path_tabix']).name)
            raw = read_tsv(before / 'signals' / f"{row['sample_ID']}.tsv")
            ready = read_tsv(Path(row['file_path']))
            self.assertEqual(len(ready), 7959)
            self.assertEqual(len(raw), len(ready))
            for original, prepared in zip(raw, ready):
                self.assertEqual(float(original['Log R Ratio']), float(prepared['Log R Ratio Adjusted']))
                self.assertEqual(float(original['B Allele Freq']), float(prepared['B Allele Freq']))
            self.assertTrue(Path(row['file_path_tabix'] + '.tbi').is_file())

    def test_raw_lrr_is_copied_when_no_adjusted_column_exists(self):
        for sid in self.ids:
            path = self.root / f'signals/{sid}.tsv'
            records = read_tsv(path)
            header = [key for key in records[0] if key != 'Log R Ratio Adjusted']
            write_tsv(path, header, [[row[key] for key in header] for row in records])
        result, output = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        signal = read_tsv(output / 'signals/001.tsv')
        self.assertTrue(all(row['Log R Ratio Adjusted'] == row['Log R Ratio'] for row in signal))

    def test_penncnv_mapping_uses_manifest_paths_not_filename_ids(self):
        (self.root / 'raw.cnv').write_text(
            'chr22:100-300 numsnp=3 length=201 state2,cn=1 signals/001.tsv startsnp=a endsnp=b\n')
        result, output = self.prepare(cnv_format='penncnv')
        self.assertEqual(result.returncode, 0, result.stderr)
        row = read_tsv(output / 'cnvs.tsv')[0]
        self.assertEqual((row['sample_ID'], row['CN'], row['GT']), ('001', '1', '1'))

    def test_checks_write_nothing_and_existing_outputs_are_rejected(self):
        result, output = self.prepare(extra=('--check',))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(output.exists())
        result, output = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        again, _ = self.prepare()
        self.assertNotEqual(again.returncode, 0)
        self.assertIn('NEW output', again.stderr)
        checked = self.launch(output, extra=('--check',))
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertFalse((self.root / 'predictions').exists())

    def test_invalid_signal_and_unknown_cnv_id_fail_before_output(self):
        signal = self.root / 'signals/001.tsv'
        signal.write_text(signal.read_text().replace('0.5', '1.5'))
        result, output = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('BAF outside', result.stderr)
        self.assertFalse(output.exists())
        write_tsv(self.root / 'cnvs.tsv', self.cnv_header, [['unknown', 22, 100, 200, 1, 1, 2]])
        result, output = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('sample ID', result.stderr)
        self.assertFalse(output.exists())

    def test_output_whitespace_is_rejected_before_preparation(self):
        output = self.root / 'output with spaces'
        result, _ = self.prepare(output=output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('whitespace', result.stderr)
        self.assertFalse(output.exists())

    def test_compression_failure_stops_preparation(self):
        tools = self.root / 'tools'
        tools.mkdir()
        fake = tools / 'bgzip'
        fake.write_text('#!/bin/sh\nexit 9\n')
        fake.chmod(0o755)
        env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'])
        result, output = self.prepare(env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('bgzip failed', result.stderr)
        self.assertFalse((output / 'samples.tsv').exists())

    def test_parallel_batches_cap_workers_skip_controls_and_preserve_ids(self):
        result, prepared = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.launch(prepared)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Running 2', result.stdout)
        output = self.root / 'predictions'
        rows = read_tsv(output / 'final_predictions.txt')
        self.assertEqual({r['sample_ID'] for r in rows}, {'001', '002'})
        self.assertEqual(len(list(output.glob('batch_*'))), 2)

    def test_worker_failure_and_missing_predictions_never_combine(self):
        result, prepared = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        bad = self.root / 'bad.R'
        bad.write_text("cat('intentional worker failure\\n'); quit(status = 7)\n")
        output = self.root / 'failed'
        result = self.launch(prepared, output=output, worker=bad)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('worker failed', result.stderr)
        self.assertFalse((output / 'final_predictions.txt').exists())
        self.assertIn('intentional worker failure', (output / 'batch_1/worker.log').read_text())
        bad.write_text('quit(status = 0)\n')
        result = self.launch(prepared, output=self.root / 'missing', worker=bad)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('without predictions', result.stderr)

    def test_empty_calls_write_header_without_launching_worker(self):
        write_tsv(self.root / 'cnvs.tsv', self.cnv_header, [])
        result, prepared = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        bad = self.root / 'never.R'
        bad.write_text('quit(status = 7)\n')
        result = self.launch(prepared, worker=bad)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_tsv(self.root / 'predictions/final_predictions.txt'), [])


if __name__ == '__main__':
    unittest.main()
