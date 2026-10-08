"""Run the existing R worker with checked process completion."""
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from common import run

PREDICTION_COLUMNS = ['sample_ID', 'start', 'pred', 'pred_prob', 'p_false',
                      'p_true_del', 'p_true_dup', 'real_numsnp', 'chr', 'end',
                      'numsnp', 'GT', 'CN']


def validate_batch(cfg, inputs):
    samples = pd.read_csv(inputs / 'samples.tsv', sep='\t', dtype={'sample_ID': str})
    cnvs = pd.read_csv(inputs / 'cnvs.tsv', sep='\t', dtype={'sample_ID': str})
    results = inputs / 'results'
    results.mkdir()
    # Samples without calls do not need a model invocation.
    samples = samples[samples['sample_ID'].isin(cnvs['sample_ID'])]
    if samples.empty:
        pd.DataFrame(columns=PREDICTION_COLUMNS).to_csv(
            results / 'final_predictions.tsv', sep='\t', index=False)
        return
    workers = min(cfg['workers'], len(samples))
    jobs = []
    for i in range(workers):
        directory = results / f'worker_{i + 1}'
        directory.mkdir()
        samples.iloc[i::workers].to_csv(directory / 'samples.tsv', sep='\t', index=False)
        command = [cfg['tools']['rscript'], cfg['tools']['validation_script'],
                   '--batch', i + 1, '--snps', inputs / 'snps.tsv',
                   '--cnvs', inputs / 'cnvs.tsv', '--samples', directory / 'samples.tsv',
                   '--model', cfg['references']['cnvalidatron_model'], '--outdir', directory]
        jobs.append((command, directory / 'worker.log', directory / 'predictions.txt'))
    # Each subprocess exit code is checked; no polling forever for missing files.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, command, log) for command, log, _ in jobs]
        for future in futures:
            future.result()
    outputs = []
    for _, _, path in jobs:
        if not path.is_file():
            raise FileNotFoundError(f'Worker exited without predictions: {path}')
        outputs.append(pd.read_csv(path, sep='\t', dtype={'sample_ID': str}))
    pd.concat(outputs, ignore_index=True).to_csv(
        results / 'final_predictions.tsv', sep='\t', index=False)
