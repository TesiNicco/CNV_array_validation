"""Create CNValidatron tables and indexed signals using explicit sample IDs."""
import re
from pathlib import Path

import pandas as pd

from common import run
from prepare_inputs import read_signal

CNV_COLUMNS = ['sample_ID', 'chr', 'start', 'end', 'GT', 'CN', 'numsnp', 'chrom']


def prepare_validation(pfb, cnv_file, prepared, root):
    out = root / 'cnvalidatron'
    out.mkdir()
    raw_dir = out / 'signals'
    raw_dir.mkdir()
    indexed = out / 'indexed_signals'
    indexed.mkdir()
    log = out / 'prepare.commands.log'
    snps = pd.read_csv(pfb, sep='\t', dtype={'Name': str})
    snps.drop(columns=['PFB']).to_csv(out / 'snps.tsv', sep='\t', index=False)
    sample_rows = []
    identities = {}
    for sample in prepared:
        identities[str(Path(sample['signal_file']).resolve())] = sample['sample_id']
        frame = read_signal(sample['signal_file'])
        frame['Chr'] = pd.to_numeric(frame['Chr'], errors='coerce')
        # Matches the original validation preparation: retain numeric chromosomes.
        frame = frame.dropna(subset=['Chr']).copy()
        if frame.empty:
            raise ValueError(f'{sample["sample_id"]}: no numeric chromosomes for CNValidatron')
        frame['Chr'] = frame['Chr'].astype(int)
        frame = frame.sort_values(['Chr', 'Position'])
        frame = frame.rename(columns={'Position': 'Start'})
        frame['End'] = frame['Start']
        frame['Log R Ratio Adjusted'] = frame['Log R Ratio']
        raw = raw_dir / (sample['sample_id'] + '.tsv')
        frame[['Chr', 'Start', 'End', 'Log R Ratio', 'B Allele Freq',
               'Log R Ratio Adjusted']].to_csv(raw, sep='\t', index=False, na_rep='NA')
        zipped = indexed / (sample['sample_id'] + '.tsv.gz')
        run(['bgzip', '-c', raw], log, stdout=zipped)
        run(['tabix', '-S', '1', '-s', '1', '-b', '2', '-e', '3', zipped], log)
        sample_rows.append({'sample_ID': sample['sample_id'], 'file_path': str(raw),
                            'file_path_tabix': str(zipped)})
    pd.DataFrame(sample_rows).to_csv(out / 'samples.tsv', sep='\t', index=False)
    parsed = []
    for line in Path(cnv_file).read_text().splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) < 5:
            raise ValueError(f'Unexpected PennCNV record: {line}')
        locus = re.fullmatch(r'chr([^:]+):(\d+)-(\d+)', fields[0])
        snp_match = re.fullmatch(r'numsnp=(\d+)', fields[1])
        cn_match = re.search(r'(?:^|,)cn=(\d+)(?:,|$)', fields[3])
        if not all((locus, snp_match, cn_match)):
            raise ValueError(f'Unexpected PennCNV record: {line}')
        signal = str(Path(fields[4]).resolve())
        if signal not in identities:
            raise ValueError(f'CNV refers to an unknown signal file: {signal}')
        chrom, start, end = locus.groups()
        if not chrom.isdigit():
            raise ValueError(f'CNValidatron numeric chromosome required: {chrom}')
        cn = int(cn_match[1])
        parsed.append({'sample_ID': identities[signal], 'chr': chrom,
                       'start': int(start), 'end': int(end), 'GT': 1 if cn in (0, 1) else 2,
                       'CN': cn, 'numsnp': int(snp_match[1]), 'chrom': int(chrom)})
    pd.DataFrame(parsed, columns=CNV_COLUMNS).to_csv(out / 'cnvs.tsv', sep='\t', index=False)
    return out
