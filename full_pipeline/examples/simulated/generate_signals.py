#!/usr/bin/env python3
"""Generate a reproducible toy array dataset without reading participant signals."""
import csv
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 20261008
# Deliberately chosen toy intervals, not copied participant calls.
EVENTS = {
    'simdup': (30000000, 30700000, 3),
    'simdel': (36000000, 36400000, 1),
    'simnormal': None,
}


def main():
    probes = []
    with (HERE / 'reference/qc_snps.hg19.bim').open() as handle:
        for line in handle:
            chrom, name, _, position, _, _ = line.split()
            probes.append((name, chrom, int(position)))
    rng = random.Random(SEED)
    # Synthetic population frequencies; shared across samples at each probe.
    frequencies = [rng.uniform(0.25, 0.75) for _ in probes]
    signals = HERE / 'signals'
    signals.mkdir(exist_ok=True)
    truth = []
    for sid, event in EVENTS.items():
        affected = []
        with (signals / f'{sid}.chr22.tsv').open('w', newline='') as handle:
            writer = csv.writer(handle, delimiter='\t', lineterminator='\n')
            writer.writerow(['Name', 'Chr', 'Position', 'GType', 'Log R Ratio', 'B Allele Freq'])
            for (name, chrom, pos), frequency in zip(probes, frequencies):
                cn = event[2] if event and event[0] <= pos <= event[1] else 2
                # Independently simulate allele dosage for the selected copy number.
                dosage = sum(rng.random() < frequency for _ in range(cn))
                baf = max(0.0, min(1.0, dosage / cn + rng.gauss(0.0, 0.012)))
                mean_lrr = {1: -0.50, 2: 0.0, 3: 0.32}[cn]
                lrr = rng.gauss(mean_lrr, 0.065)
                writer.writerow([name, chrom, pos, 'NC', f'{lrr:.6f}', f'{baf:.6f}'])
                if cn != 2:
                    affected.append(pos)
        if event:
            truth.append([sid, 22, event[0], event[1], min(affected), max(affected), event[2], len(affected)])
    with (HERE / 'truth.tsv').open('w', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t', lineterminator='\n')
        writer.writerow(['sample_id', 'chr', 'simulation_start', 'simulation_end',
                         'first_affected_probe', 'last_affected_probe', 'CN', 'numsnp'])
        writer.writerows(truth)
    print(f'Generated {len(EVENTS)} synthetic samples, {len(probes)} probes each; seed {SEED}.')


if __name__ == '__main__':
    main()
