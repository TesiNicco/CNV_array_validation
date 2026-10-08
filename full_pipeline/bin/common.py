"""Shared configuration, manifest and command handling."""
import csv
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml


def resolve(base, value):
    path = Path(value).expanduser()
    return str((base / path).resolve()) if not path.is_absolute() else str(path.resolve())


def load_config(filename):
    filename = Path(filename).resolve()
    with filename.open() as handle:
        cfg = yaml.safe_load(handle)
    base = filename.parent
    cfg['output_dir'] = resolve(base, cfg['output_dir'])
    if re.search(r'\s', cfg['output_dir']):
        raise ValueError('output_dir must not contain whitespace: PennCNV call records use whitespace delimiters')
    cfg['samples_manifest'] = resolve(base, cfg['samples_manifest'])
    if cfg['tools'].get('penncnv_dir') is None:
        prefix = os.environ.get('CONDA_PREFIX')
        if not prefix:
            raise ValueError('Activate the analysis environment or set tools.penncnv_dir explicitly')
        cfg['tools']['penncnv_dir'] = str(Path(prefix) / 'opt/PennCNV-1.0.5')
    for key in ('penncnv_dir', 'validation_script'):
        cfg['tools'][key] = resolve(base, cfg['tools'][key])
    rscript = cfg['tools']['rscript']
    if '/' in rscript:
        cfg['tools']['rscript'] = resolve(base, rscript)
    for key in ('gc_file', 'excluded_regions', 'cnvalidatron_model'):
        cfg['references'][key] = resolve(base, cfg['references'][key])
    for options in cfg['batches'].values():
        for key in ('qc_bim',):
            if options.get(key):
                options[key] = resolve(base, options[key])
    if not isinstance(cfg['adjust_lrr'], bool):
        raise ValueError('adjust_lrr must be true or false')
    if not isinstance(cfg['workers'], int) or cfg['workers'] < 1:
        raise ValueError('workers must be a positive integer')
    build = cfg['signal_genome_build']
    for key in ('gc_genome_build', 'excluded_regions_genome_build'):
        if cfg['references'][key] != build:
            raise ValueError(f'{key} must match signal_genome_build ({build})')
    for batch, options in cfg['batches'].items():
        if not re.fullmatch(r'[A-Za-z0-9-]+(?:_[A-Za-z0-9-]+)*', batch):
            raise ValueError(f'Unsafe batch name: {batch}')
        if options['min_input_snps'] < 0:
            raise ValueError('min_input_snps must be nonnegative')
        if not isinstance(options['common_snps_only'], bool):
            raise ValueError('common_snps_only must be true or false')
        if options.get('qc_bim') and options['qc_genome_build'] != build:
            raise ValueError(f'{batch}: qc_genome_build must match signal_genome_build ({build}); liftover is not performed')
    return cfg


def read_manifest(cfg):
    path = Path(cfg['samples_manifest'])
    with path.open(newline='') as handle:
        reader = csv.DictReader(handle, delimiter='\t')
        required = {'sample_id', 'batch', 'signal_file'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('Manifest requires sample_id, batch, signal_file columns')
        rows = list(reader)
    if not rows:
        raise ValueError('Manifest is empty')
    seen = set()
    signals = set()
    for row in rows:
        sid = row['sample_id']
        # The inherited CNValidatron image parser splits sample IDs at underscore.
        if not re.fullmatch(r'[A-Za-z0-9-]+', sid):
            raise ValueError(f'Sample ID {sid!r}: use letters, digits and hyphens only')
        pair = (row['batch'], sid)
        if pair in seen:
            raise ValueError(f'Duplicate sample ID in batch: {pair}')
        seen.add(pair)
        if row['batch'] not in cfg['batches']:
            raise ValueError(f'Unconfigured batch: {row["batch"]}')
        row['signal_file'] = resolve(path.parent, row['signal_file'])
        signal_pair = (row['batch'], row['signal_file'])
        if signal_pair in signals:
            raise ValueError(f'Signal file listed twice in the same batch: {signal_pair}')
        signals.add(signal_pair)
    return rows


def preflight(cfg, rows):
    files = [r['signal_file'] for r in rows]
    files += [cfg['references'][k] for k in ('gc_file', 'excluded_regions', 'cnvalidatron_model')]
    files.append(cfg['tools']['validation_script'])
    scripts = ('compile_pfb.pl', 'cal_gc_snp.pl', 'genomic_wave.pl',
               'detect_cnv.pl', 'filter_cnv.pl', 'clean_cnv.pl', 'scan_region.pl')
    files += [str(Path(cfg['tools']['penncnv_dir']) / name) for name in scripts]
    files.append(str(Path(cfg['tools']['penncnv_dir']) / 'lib/hhall.hmm'))
    for batch in {r['batch'] for r in rows}:
        files += [cfg['batches'][batch][k] for k in ('qc_bim',)
                  if cfg['batches'][batch].get(k)]
    for path in files:
        if '/path/to/' in path:
            raise ValueError(f'Replace the placeholder path: {path}')
        if not Path(path).is_file():
            raise FileNotFoundError(path)
    for executable in ('perl', 'bgzip', 'tabix', cfg['tools']['rscript']):
        if not shutil.which(executable):
            raise ValueError(f'Executable not found: {executable}')
    # Check the actual Perl extension, rather than only the presence of scripts.
    subprocess.run(['perl', '-e', 'use lib $ARGV[0]; require khmm; die "PennCNV HMM function missing\\n" unless defined &khmm::testVit_CHMM;',
                    str(Path(cfg['tools']['penncnv_dir']) / 'kext')], check=True)
    expression = ('pkgs <- c("data.table", "stringr", "BiocManager", "BiocParallel", '
                  '"torch", "luz", "CNValidatron", "argparse"); '
                  'missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly=TRUE)]; '
                  'if (length(missing)) stop(paste("Missing R packages:", paste(missing, collapse=", ")))')
    subprocess.run([cfg['tools']['rscript'], '-e', expression], check=True)


def run(command, log, stdout=None):
    command = [str(x) for x in command]
    print('Running:', command[0], ' '.join(command[1:]), flush=True)
    with Path(log).open('a') as handle:
        handle.write('\nCOMMAND ' + json.dumps(command) + '\n')
        handle.flush()
        if stdout is None:
            subprocess.run(command, stdout=handle, stderr=handle, check=True)
        else:
            with Path(stdout).open('wb') as output:
                subprocess.run(command, stdout=output, stderr=handle, check=True)
