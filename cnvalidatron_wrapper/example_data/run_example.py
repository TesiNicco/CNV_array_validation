#!/usr/bin/env python3
"""Prepare indexes and validate fixed synthetic CNVs without running PennCNV."""
import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / 'simulated'
WORKER = HERE.parent / 'bin/validation_CNV.r'


def run(command, log, output=None):
    command = [str(arg) for arg in command]
    with log.open('a') as handle:
        handle.write('COMMAND ' + json.dumps(command) + '\n')
        handle.flush()
        if output is None:
            subprocess.run(command, stdout=handle, stderr=handle, check=True)
        else:
            with output.open('wb') as target:
                subprocess.run(command, stdout=target, stderr=handle, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, help='Path to the compatible trained model')
    parser.add_argument('--output', type=Path, default=DATA / 'results', help='New output directory')
    parser.add_argument('--check', action='store_true', help='Check inputs and dependencies without writing results')
    args = parser.parse_args()
    model = Path(args.model).expanduser().resolve()
    output = args.output.expanduser().resolve()
    with (DATA / 'samples.tsv').open() as handle:
        samples = list(csv.DictReader(handle, delimiter='\t'))
    for path in [model, WORKER, DATA / 'snps.tsv', DATA / 'cnvs.tsv'] + [DATA / row['file_path'] for row in samples]:
        if not path.is_file():
            raise FileNotFoundError(path)
    for executable in ('bgzip', 'tabix', 'Rscript'):
        if not shutil.which(executable):
            raise ValueError(f'Executable not found: {executable}; activate the analysis environment')
    if output.exists():
        raise ValueError(f'Choose a NEW output directory: {output}')
    # Only validation dependencies are checked; no PennCNV scripts/extension.
    expression = ('pkgs <- c("data.table", "stringr", "BiocManager", "BiocParallel", '
                  '"torch", "luz", "CNValidatron", "argparse"); '
                  'missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly=TRUE)]; '
                  'if (length(missing)) stop(paste("Missing R packages:", paste(missing, collapse=", ")))')
    subprocess.run(['Rscript', '--vanilla', '-e', expression], check=True)
    if args.check:
        print(f'Preflight passed: {len(samples)} synthetic samples, 2 fixed CNVs. No outputs written.')
        return
    output.mkdir(parents=True, exist_ok=False)
    log = output / 'commands.log'
    signals = output / 'signals'
    signals.mkdir()
    manifest = []
    for sample in samples:
        raw = signals / (sample['sample_ID'] + '.tsv')
        shutil.copyfile(DATA / sample['file_path'], raw)
        zipped = raw.with_suffix('.tsv.gz')
        run(['bgzip', '-c', raw], log, zipped)
        run(['tabix', '-S', '1', '-s', '1', '-b', '2', '-e', '3', zipped], log)
        manifest.append([sample['sample_ID'], str(raw), str(zipped)])
    with (output / 'samples.tsv').open('w', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t', lineterminator='\n')
        writer.writerow(['sample_ID', 'file_path', 'file_path_tabix'])
        writer.writerows(manifest)
    for name in ('snps.tsv', 'cnvs.tsv'):
        shutil.copyfile(DATA / name, output / name)
    predictions = output / 'validation'
    predictions.mkdir()
    run(['Rscript', '--vanilla', WORKER, '--batch', '1', '--snps', output / 'snps.tsv',
         '--cnvs', output / 'cnvs.tsv', '--samples', output / 'samples.tsv',
         '--model', model, '--outdir', predictions], log)
    result = predictions / 'predictions.txt'
    if not result.is_file():
        raise FileNotFoundError(f'Worker exited without predictions: {result}')
    print(f'Finished validation-only example: {result}')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
