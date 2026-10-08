"""Prepare one batch without cohort-specific paths or filename parsing."""
from pathlib import Path

import pandas as pd


def chromosome(series):
    return series.astype(str).str.replace(r'^chr', '', regex=True)


def read_signal(path):
    frame = pd.read_csv(path, sep='\t', dtype={'Name': str, 'Chr': str})
    for column in ('Name', 'Chr', 'Position'):
        if column not in frame:
            raise ValueError(f'{path}: missing column {column}')
    # PennCNV exports may prefix signal column names with the sample ID.
    for suffix in ('Log R Ratio', 'B Allele Freq'):
        matches = [c for c in frame if c == suffix or c.endswith('.' + suffix)]
        if len(matches) != 1:
            raise ValueError(f'{path}: expected one {suffix} column, found {matches}')
        frame = frame.rename(columns={matches[0]: suffix})
    genotype = [c for c in frame if c == 'GType' or c.endswith('.GType')]
    if len(genotype) > 1:
        raise ValueError(f'{path}: multiple genotype columns')
    frame['GType'] = frame[genotype[0]] if genotype else 'NC'
    frame = frame.dropna(subset=['Chr', 'Name']).copy()
    frame['Chr'] = chromosome(frame['Chr'])
    frame['Position'] = pd.to_numeric(frame['Position'], errors='coerce')
    frame = frame.dropna(subset=['Chr', 'Position', 'Name']).copy()
    if (frame['Position'] < 1).any() or (frame['Position'] % 1 != 0).any():
        raise ValueError(f'{path}: positions must be positive 1-based integers')
    frame['Position'] = frame['Position'].astype(int)
    for column in ('Log R Ratio', 'B Allele Freq'):
        frame[column] = pd.to_numeric(frame[column], errors='raise')
    frame['key'] = frame['Chr'] + ':' + frame['Position'].astype(str)
    return frame


def qc_positions(options, signal_build):
    if not options.get('qc_bim'):
        return None
    bim = pd.read_csv(options['qc_bim'], sep=r'\s+', header=None, dtype={0: str})
    if bim.shape[1] != 6:
        raise ValueError('QC BIM must contain six columns')
    chrom = chromosome(bim[0])
    positions = pd.to_numeric(bim[3], errors='raise')
    if (positions < 1).any() or (positions % 1 != 0).any():
        raise ValueError('BIM positions must be positive 1-based integers')
    if options['qc_genome_build'] != signal_build:
        raise ValueError('QC and signal genome builds differ; liftover is not performed')
    return set(chrom + ':' + positions.astype(int).astype(str))


def prepare_batch(cfg, batch, samples, root):
    options = cfg['batches'][batch]
    signal_dir = root / 'prepared_signals'
    signal_dir.mkdir()
    qc_keys = qc_positions(options, cfg['signal_genome_build'])
    common = None
    accepted = []
    audit = []
    # Two passes keep memory bounded when computing a common-probe set.
    for sample in samples:
        frame = read_signal(sample['signal_file'])
        keep = len(frame) >= options['min_input_snps']
        audit.append({'sample_id': sample['sample_id'], 'input_snps': len(frame),
                      'status': 'accepted' if keep else 'below_min_input_snps'})
        if keep:
            accepted.append(sample)
            if options['common_snps_only']:
                keys = set(frame['key'])
                common = keys if common is None else common & keys
    pd.DataFrame(audit).to_csv(root / 'sample_qc.tsv', sep='\t', index=False)
    if not accepted:
        raise ValueError(f'{batch}: no samples passed input SNP count filtering')
    if common is not None:
        qc_keys = common if qc_keys is None else qc_keys & common
    prepared = []
    reference_probes = None
    for sample in accepted:
        frame = read_signal(sample['signal_file'])
        if qc_keys is not None:
            frame = frame[frame['key'].isin(qc_keys)]
        frame = frame.drop_duplicates('key').copy()
        if frame.empty:
            raise ValueError(f'{batch}/{sample["sample_id"]}: no SNPs remain')
        frame['_sort'] = pd.to_numeric(frame['Chr'], errors='coerce')
        frame = frame.sort_values(['_sort', 'Chr', 'Position'])
        probes = frame[['Name', 'Chr', 'Position']].reset_index(drop=True)
        if reference_probes is None:
            reference_probes = probes
        elif not probes.equals(reference_probes):
            raise ValueError(f'{batch}/{sample["sample_id"]}: filtered probes differ between samples. '
                             'PennCNV PFB requires identical probe rows. Review inputs or explicitly '
                             'enable common_snps_only; probe names must also agree.')
        target = signal_dir / (sample['sample_id'] + '.signal.tsv')
        frame[['Name', 'Chr', 'Position', 'GType', 'Log R Ratio', 'B Allele Freq']].to_csv(
            target, sep='\t', index=False, na_rep='NA')
        prepared.append({'sample_id': sample['sample_id'], 'signal_file': str(target)})
    pd.DataFrame(prepared).to_csv(root / 'prepared_samples.tsv', sep='\t', index=False)
    return prepared
