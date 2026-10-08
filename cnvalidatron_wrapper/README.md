# CNValidatron wrapper

Validate existing PennCNV calls with CNValidatron using their corresponding
LRR/BAF signals and SNP/sample tables. This workflow does not call CNVs or require
PennCNV to be installed. It uses the same validation worker as the full pipeline.

All commands below run from the **repository root**, `CNV_array_validation/`.

## Credit and citation

**CNValidatron and its pretrained model were developed by Simone Montalbano
(SinomeM) and collaborators.** The original software is
[CNValidatron_fl](https://github.com/SinomeM/CNValidatron_fl/tree/main).
This repository provides input preparation, execution wrappers and pipeline
integration maintained by Niccolo Tesi; it does not claim authorship of
CNValidatron or its trained model.

If you use CNValidatron, cite Montalbano et al.,
[CNValidatron: accurate and efficient validation of PennCNV calls using computer vision](https://doi.org/10.1186/s12859-026-06375-6),
*BMC Bioinformatics* **27**, 47 (2026), and follow the upstream citation guidance.
PennCNV is separate upstream software from
[WGLab](https://github.com/WGLab/PennCNV); follow its
[credit and citation instructions](https://penncnv.openbioinformatics.org/en/latest/misc/credit/)
when using the full workflow. External tools retain their upstream licenses;
this repository's license is in [LICENSE](../LICENSE).

## Setup

```bash
bash setup/setup_environment.sh --skip-penncnv
conda activate penncnv-cnvalidatron
```

If the working environment already exists, activate it; you do not need to
install it again. The shared setup installs the required R packages and CPU
Torch runtime, plus bgzip/tabix for signal indexing.

Download a compatible trained model from the authors'
[Zenodo model record](https://doi.org/10.5281/zenodo.17174637). The model is
external; setup and example scripts do not download it.

## How the scripts relate

| Script | Role | When to use it |
|---|---|---|
| `bin/preparation.R` | Reformats signal/SNP/sample/CNV tables and compresses/indexes the signals. | Only when your existing files need conversion or indexing. Supply paths and the CNV format as command-line arguments. |
| `bin/validation_CNV.r` | Generates images for the supplied CNVs, loads the trained model and writes predictions for one batch. | Run directly with formatted, indexed inputs, or let a launcher invoke it. It does not depend on either other script. |
| `bin/parallelize_validation.r` | Splits samples into batches, starts separate R processes running `validation_CNV.r`, waits for their predictions, and combines them. | Optional launcher for parallel validation; supply paths and `--workers` as arguments. |

**Preparation is not always required.**

The user decides whether conversion is needed: neither the validation worker
nor the parallel launcher automatically detects or runs `preparation.R`.
Compare your tables with the required columns below and the format examples in
`example_data/before_preparation/` and `example_data/after_preparation/`.
Also verify that the signal files are sorted, bgzip-compressed and tabix-indexed;
matching table columns alone is not sufficient. Both commands now offer their
own `--check` mode for their supported inputs. The runnable example's `--check`
checks file existence and dependencies, not full input-format compatibility.

Choose the step based on your inputs:

- **Unformatted signals/tables:** convert them and create bgzip/tabix indexes,
  then run validation directly or through the parallel launcher.
- **Formatted, indexed inputs:** go straight to `validation_CNV.r` or the launcher.
- **Supplied synthetic example:** its own example script creates the indexes and
  resolved sample paths, then calls `validation_CNV.r` directly. It runs neither
  `preparation.R` nor `parallelize_validation.r`.

Parallelization means multiple independent **R processes**, each handling a
sample batch. The worker disables parallel image generation internally; this
is separate from any numerical-library threading.

## Run and test the synthetic example

The runnable dataset is in `example_data/simulated/`. It contains three synthetic
chr22 samples, 7,959 probes per sample, and two fixed simulated CNV calls. All
coordinates are hg19. No participant signals, genotypes or IDs are included.

With the environment activated, replace `/path/to/joint.rds` with your actual
compatible model path:

```bash
# Check files, executables and R package loading; write no outputs.
bash cnvalidatron_wrapper/example_data/run_example.sh --model /path/to/joint.rds --check

# Prepare indexes and run the validation worker.
bash cnvalidatron_wrapper/example_data/run_example.sh --model /path/to/joint.rds

# Inspect the resulting classifications.
cat cnvalidatron_wrapper/example_data/simulated/results/validation/predictions.txt
```

The tested model produces two prediction rows:

| Sample | Expected class | `pred` | Copy number (`CN`) | SNP count (`numsnp`) |
|---|---|---:|---:|---:|
| `simdup` | True duplication | 3 | 3 | 91 |
| `simdel` | True deletion | 2 | 1 | 59 |

`simnormal` has no CNV input, so it has no prediction row. Class 1 means a false
call. Probabilities may vary with the model/environment; the example is an
execution check, not a measure of accuracy on real data.

To check the expected sample IDs and classes automatically after the run:

```bash
python - <<'CHECK'
import csv
from pathlib import Path
path = Path('cnvalidatron_wrapper/example_data/simulated/results/validation/predictions.txt')
with path.open() as handle:
    rows = list(csv.DictReader(handle, delimiter='\t'))
assert len(rows) == 2, 'Expected two prediction rows'
assert {r['sample_ID']: int(r['pred']) for r in rows} == {'simdup': 3, 'simdel': 2}
print('PASS: both simulated CNVs have the expected classes.')
CHECK
```

An existing output directory is rejected. To repeat the example, choose a new
output location:

```bash
bash cnvalidatron_wrapper/example_data/run_example.sh --model /path/to/joint.rds \
  --output cnvalidatron_wrapper/example_data/simulated/results_02
```

| Example option | Meaning |
|---|---|
| `--model PATH` | Required path to the compatible trained model. |
| `--output PATH` | New output directory, relative to the current working directory or absolute. Default: `example_data/simulated/results` within this wrapper. |
| `--check` | Check input-file existence, bgzip/tabix/Rscript and R package loading without writing results. Does not load the model. |
| `--help` | Show usage. |

See the [example documentation](example_data/simulated/README.md) for its files
and generation details. To test standalone preparation on raw signals and
raw PennCNV-format calls,
use the runnable [before-preparation dataset](example_data/before_preparation/README.md).
The [after-preparation tables](example_data/after_preparation/README.md) show the
expected output schema; their signal files are generated when preparation runs.

## Required inputs for your own validation run

| Input | Required content |
|---|---|
| Signals | Tab-separated `Chr`, `Start`, `End`, `Log R Ratio`, `B Allele Freq`, `Log R Ratio Adjusted`; sorted by chromosome and position, bgzip-compressed and tabix-indexed. |
| SNP table | Probe `Name`, `Chr` and `Position` columns for the corresponding signal probes. |
| Sample table | `sample_ID`, `file_path` and `file_path_tabix`, linking samples to their plain and indexed signals. Use absolute paths for direct worker runs. |
| CNV table | `sample_ID`, `chr`, `start`, `end`, `GT`, `CN`, `numsnp`; `GT` is 1 for deletions and 2 for duplications. |
| Model | Compatible pretrained file loaded with `luz::luz_load`. |

Use matching genome builds for all coordinates. The worker does not perform
liftover, signal correction or CNV calling. Use simple sample IDs with letters,
digits and hyphens; its image-name parser does not support underscores or periods.
The new commands preserve IDs with leading zeros. Indexed signal paths and
output directory paths must not contain whitespace: upstream CNValidatron builds
tabix commands from those paths without quoting them.

**LRR adjustment:** neither preparation nor validation performs GC wave
correction. Preparation preserves `Log R Ratio Adjusted` when present; otherwise
it copies the supplied LRR into that column. For a real adjusted-LRR run, supply
values already corrected upstream. The synthetic example deliberately copies
its unadjusted toy LRR into that column and documents this assumption.

### Preparing inputs when necessary

Supply the input paths without editing the script:

```bash
Rscript cnvalidatron_wrapper/bin/preparation.R \
  --samples /absolute/path/to/samples.tsv \
  --snps /absolute/path/to/snps.tsv \
  --cnvs /absolute/path/to/calls.rawcnv \
  --cnv-format penncnv \
  --outdir /absolute/path/to/new/prepared_inputs
```

| Preparation argument | Meaning |
|---|---|
| `--samples` | Required TSV with `sample_ID` and `file_path`; signal paths are resolved relative to this manifest. |
| `--snps` | Required TSV with `Name`, `Chr`, `Position`; an optional `Index` column is removed. |
| `--cnvs` | Required CNV file, in the explicitly selected format below. |
| `--cnv-format penncnv` | Read raw PennCNV records; match each record's signal path to the manifest to obtain its sample ID. No sample-ID extraction from filenames is performed. Relative paths in calls are resolved relative to the CNV file. |
| `--cnv-format table` | Read a headered validation TSV with the required CNV columns listed above. |
| `--outdir` | Required new directory for prepared tables/signals; must not exist. |
| `--check` | Read and validate the supported input tables and signals, and check bgzip/tabix availability, without creating outputs. |

Signals must use named columns: `Chr`, `Position` (or `Start`), `Log R Ratio`,
`B Allele Freq`, and optionally `End` and `Log R Ratio Adjusted`. Signal columns
may carry a sample prefix, such as `sample1.Log R Ratio`. Chromosomes must be
numeric, optionally with a `chr` prefix. Missing/nonnumeric coordinates, missing
or nonfinite signal values, BAF outside [0, 1], and duplicate signal positions
are rejected. No rows are silently filtered. Exports with different column names
need conversion to this supported format first.

Preparation sorts the signals, writes plain tables and bgzip/tabix files under
`<outdir>/signals/`, and writes `samples.tsv`, `snps.tsv` and `cnvs.tsv` directly
under `<outdir>`. The generated sample table contains absolute signal paths.
Source files are not changed. A failed compression/indexing command stops the
run; inspect `preparation.log`. Existing outputs are not reused or overwritten.
Package installation belongs to `setup/`; neither analysis command installs R
packages automatically.

To test preparation with the supplied **raw signals and PennCNV-format
simulated calls**, run:

```bash
Rscript cnvalidatron_wrapper/bin/preparation.R \
  --samples cnvalidatron_wrapper/example_data/before_preparation/samples.txt \
  --snps cnvalidatron_wrapper/example_data/before_preparation/snps.txt \
  --cnvs cnvalidatron_wrapper/example_data/before_preparation/cnvs.txt \
  --cnv-format penncnv \
  --outdir results/prepared_example
```

This produces the tables used in the parallel-launcher command below. The
[before-preparation README](example_data/before_preparation/README.md) describes
the raw files, and the [after-preparation references](example_data/after_preparation/README.md)
show their expected converted schema. For already headered CNV tables, use
`--cnv-format table` instead.

For already formatted signal tables, the index commands used by the example are:

```bash
bgzip -c /path/to/sample.tsv > /path/to/sample.tsv.gz
tabix -S 1 -s 1 -b 2 -e 3 /path/to/sample.tsv.gz
```

### Run the worker directly

Create the output directory first, then supply prepared inputs:

```bash
Rscript cnvalidatron_wrapper/bin/validation_CNV.r \
  --batch 1 \
  --snps /absolute/path/to/snps.tsv \
  --cnvs /absolute/path/to/cnvs.tsv \
  --samples /absolute/path/to/samples.tsv \
  --model /absolute/path/to/joint.rds \
  --outdir /absolute/path/to/new/output
```

All six arguments are required. `--batch` is an integer batch label; the worker
validates the calls belonging to the samples supplied in `--samples`. It writes
`predictions.txt` and generated images under `--outdir`. The output table
contains class predictions and probabilities; no additional probability cutoff
is applied to the written table.

`--snps` supplies probe names and coordinates, and `--cnvs` supplies the calls
linked to sample IDs. **Signal paths are supplied inside the `--samples` table**,
not as separate command-line arguments. For example, save the following as a
tab-separated `samples.tsv`:

```text
sample_ID	file_path	file_path_tabix
sample1	/absolute/path/to/sample1.tsv	/absolute/path/to/sample1.tsv.gz
sample2	/absolute/path/to/sample2.tsv	/absolute/path/to/sample2.tsv.gz
```

`file_path` identifies the plain formatted signal table; `file_path_tabix`
identifies its bgzip-compressed copy. Each compressed file must have a matching
tabix index, such as `sample1.tsv.gz.tbi`. Sample IDs must match the CNV table.
Once these files are ready, the direct command above requires no edits to the
worker and no call to `preparation.R`.

### Run the parallel launcher

Supply prepared input tables, the model and a fresh output directory:

```bash
Rscript cnvalidatron_wrapper/bin/parallelize_validation.r \
  --samples results/prepared_example/samples.tsv \
  --snps results/prepared_example/snps.tsv \
  --cnvs results/prepared_example/cnvs.tsv \
  --model /absolute/path/to/joint.rds \
  --outdir results/validated_example \
  --workers 2
```

These paths use the prepared example from the command above. For your own data,
replace them with your prepared tables; no script edits are needed. Input/output
arguments are relative to your current working directory unless absolute.
Signal paths inside a sample table are relative to that table unless absolute.

| Launcher argument | Meaning |
|---|---|
| `--samples`, `--snps`, `--cnvs`, `--model`, `--outdir` | Required prepared input paths, trained model and new output directory. |
| `--workers` | Maximum concurrent R processes; positive integer, default 1. |
| `--check` | Validate table columns, IDs, coordinate/CN values and signal/index/model-file existence without creating outputs or starting workers. Does not load the model or inspect all signal values/index contents. |
| `--worker-script` | Optional alternative worker path; defaults to the sibling `validation_CNV.r`. Normally leave unchanged. |
| `--help` | Show usage; also available on preparation. |

The launcher works on Linux/Unix, skips samples without calls, and caps the
number of workers to the number of samples with calls so no empty batch is
started. It preserves sample IDs as character values. Numerical-library thread
limits are set to one for each worker process.

Each batch writes `samples.tsv`, `worker.log` and `predictions.txt` under
`<outdir>/batch_<number>/`. Successful predictions are combined into
`<outdir>/final_predictions.txt`. A nonzero worker exit or missing prediction file
fails the launcher; logs are retained and no combined result is written. It waits
for running processes to finish, not indefinitely for files to appear. A CNV
input with no calls produces a header-only combined table without launching a
worker. Existing output directories are rejected, even for `--check`.

The synthetic preparation followed by this two-worker launcher was tested with
the compatible model and produced the expected duplication and deletion.
The simpler `example_data/run_example.sh` still tests the direct worker; it does
not invoke the parallel launcher.

## Command tests

With the shared environment activated, run from the repository root:

```bash
python -m unittest discover -s cnvalidatron_wrapper/tests -v
```

The tests run the actual preparation/launcher commands and bgzip/tabix. They
check input validation, path/ID handling, preservation of adjusted LRR, raw-call
mapping, empty calls, worker failures and missing predictions. Small substitute
workers exercise launcher behavior without loading a model; real model
inference is checked through the synthetic example and the two-worker run above.

## Historical benchmark

| Samples | CNVs | CPUs | Time (s) |
|---|---:|---:|---:|
| 1 | 13 | 1 | 14 |
| 5 | 144 | 1 | 88 |
| 10 | 235 | 1 | 144 |
| 45 | 900 | 1 | 3180 |

These measurements were reported for the earlier wrapper, not the new synthetic
example or your hardware. The worker is adapted from
[CNValidatron](https://github.com/SinomeM/CNValidatron_fl) to accommodate the
supplied CNV table structure and preserve sample IDs when reading input tables.
