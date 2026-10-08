#!/usr/bin/env python3
"""Run the synthetic example with an externally supplied CNValidatron model."""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE / 'bin'))
from common import load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, help='Path to the downloaded compatible trained model')
    parser.add_argument('--output', help='New output directory; default examples/simulated/results')
    parser.add_argument('--check', action='store_true', help='Check inputs and dependencies without writing results')
    args = parser.parse_args()
    cfg = load_config(PIPELINE / 'examples/simulated/config.yaml')
    cfg['references']['cnvalidatron_model'] = str(Path(args.model).expanduser().resolve())
    if args.output:
        cfg['output_dir'] = str(Path(args.output).expanduser().resolve())
    # Pass absolute resolved paths to the regular entry point, without editing
    # the distributed configuration or recording a private model path there.
    with tempfile.TemporaryDirectory(prefix='cnv-example-') as temporary:
        config = Path(temporary) / 'config.yaml'
        config.write_text(yaml.safe_dump(cfg, sort_keys=False))
        command = [sys.executable, str(PIPELINE / 'bin/run_pipeline.py'), '--config', str(config)]
        if args.check:
            command.append('--check')
        return subprocess.call(command)


if __name__ == '__main__':
    sys.exit(main())
