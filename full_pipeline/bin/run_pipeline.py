#!/usr/bin/env python3
"""Configuration-driven entry point. --check performs read-only preflight."""
import argparse
import sys
from pathlib import Path

import yaml

from common import load_config, preflight, read_manifest
from prepare_inputs import prepare_batch
from run_penncnv import call_batch
from prepare_cnvalidatron import prepare_validation
from run_validation import validate_batch


def main():
    parser = argparse.ArgumentParser(description='Run PennCNV followed by CNValidatron')
    parser.add_argument('--config', required=True, help='Path to pipeline YAML configuration')
    parser.add_argument('--batch', help='Process only this batch from the manifest')
    parser.add_argument('--check', action='store_true', help='Validate configuration/dependencies without writing outputs')
    args = parser.parse_args()
    cfg = load_config(args.config)
    rows = read_manifest(cfg)
    if args.batch:
        rows = [r for r in rows if r['batch'] == args.batch]
        if not rows:
            raise ValueError(f'No manifest samples for batch {args.batch}')
    preflight(cfg, rows)
    batches = sorted({r['batch'] for r in rows})
    output = Path(cfg['output_dir'])
    if output.exists():
        raise ValueError(f'Output directory already exists; choose a NEW directory: {output}')
    if args.check:
        print(f'Preflight passed: {len(rows)} samples, {len(batches)} batches. No outputs written.')
        return
    output.mkdir(parents=True, exist_ok=False)
    (output / 'config.resolved.yaml').write_text(yaml.safe_dump(cfg, sort_keys=False))
    for batch in batches:
        print(f'Processing batch {batch}', flush=True)
        root = output / batch
        root.mkdir()
        prepared = prepare_batch(cfg, batch, [r for r in rows if r['batch'] == batch], root)
        pfb, cnvs, prepared = call_batch(cfg, batch, prepared, root)
        inputs = prepare_validation(pfb, cnvs, prepared, root)
        validate_batch(cfg, inputs)
        print(f'Finished {batch}: {inputs / "results/final_predictions.tsv"}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
