#!/usr/bin/env bash
# Create/update the environment with mamba, then install and verify the full stack.
set -euo pipefail
SETUP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="penncnv-cnvalidatron"
INSTALL_PENNCNV=true

usage() {
    echo "Usage: bash setup_environment.sh [--name ENVIRONMENT] [--install-penncnv | --skip-penncnv]"
    echo "Installs CPU Torch, CNValidatron and (by default) PennCNV under the selected environment."
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --name)
            if [[ $# -lt 2 || -z "$2" || "$2" == -* ]]; then
                echo "--name requires an environment name" >&2
                exit 2
            fi
            ENV_NAME="$2"
            shift 2
            ;;
        -h|--help) usage; exit 0 ;;
        --install-penncnv) INSTALL_PENNCNV=true; shift ;;
        --skip-penncnv) INSTALL_PENNCNV=false; shift ;;
        *) usage >&2; echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

if ! command -v mamba >/dev/null 2>&1; then
    echo "mamba is not on PATH. Install it or activate the environment that provides it, then rerun." >&2
    exit 1
fi

# These flags avoid version-dependent -y support in older mamba env subcommands.
export CONDA_ALWAYS_YES=true
export MAMBA_ALWAYS_YES=true

if mamba run --name "$ENV_NAME" true >/dev/null 2>&1; then
    echo "Updating environment: $ENV_NAME"
    mamba env update --name "$ENV_NAME" --file "$SETUP_DIR/environment.yml"
else
    echo "Creating environment: $ENV_NAME"
    mamba env create --name "$ENV_NAME" --file "$SETUP_DIR/environment.yml"
fi

RUN_ARGS=(run --name "$ENV_NAME")
RUN_HELP="$(mamba run --help)"
if [[ "$RUN_HELP" == *"--no-capture-output"* ]]; then
    RUN_ARGS+=(--no-capture-output)
fi

if [[ "$INSTALL_PENNCNV" == true ]]; then
    echo "Installing PennCNV under the selected environment's opt/ directory"
    mamba "${RUN_ARGS[@]}" bash "$SETUP_DIR/install_penncnv.sh"
else
    echo "PennCNV installation skipped; configure tools.penncnv_dir for your existing installation."
fi

echo "Installing CPU Torch runtime inside $ENV_NAME"
mamba "${RUN_ARGS[@]}" Rscript --vanilla "$SETUP_DIR/install_torch_runtime.R"

echo "Loading Torch in a fresh R process and installing remaining R packages"
mamba "${RUN_ARGS[@]}" Rscript --vanilla "$SETUP_DIR/install_r_dependencies.R"

echo "Checking R packages and Torch calculation"
# Use a fresh R process so Torch loads the newly installed runtime.
TORCH_INSTALL=0 TORCH_LOAD=1 TORCH_VERIFY_LOAD=TRUE CUDA=cpu mamba "${RUN_ARGS[@]}" \
    Rscript --vanilla "$SETUP_DIR/check_environment.R"

echo "Checking Python packages and command-line tools"
mamba "${RUN_ARGS[@]}" python -c 'import pandas, yaml; print("Python packages OK")'
mamba "${RUN_ARGS[@]}" Rscript --vanilla -e \
    'tools <- c("perl", "bgzip", "tabix"); missing <- tools[Sys.which(tools) == ""]; if (length(missing)) stop(paste("Missing tools:", paste(missing, collapse=", "))); cat("Command-line tools OK\n")'

echo "Environment setup and checks passed."
printf 'Activate it with: conda activate %q\n' "$ENV_NAME"
