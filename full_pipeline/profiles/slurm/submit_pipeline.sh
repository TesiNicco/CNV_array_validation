#!/usr/bin/env bash
#SBATCH --cpus-per-task=4
#SBATCH --job-name=penncnv-cnvalidatron
set -euo pipefail
if [[ $# -lt 2 ]]; then
    echo "Usage: sbatch submit_pipeline.sh /absolute/path/to/full_pipeline /absolute/path/to/config.yaml [batch]" >&2
    exit 2
fi
PIPELINE_DIR="$1"
CONFIG_FILE="$2"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
if [[ $# -eq 3 ]]; then
    exec bash "$PIPELINE_DIR/run_pipeline.sh" --config "$CONFIG_FILE" --batch "$3"
fi
exec bash "$PIPELINE_DIR/run_pipeline.sh" --config "$CONFIG_FILE"
