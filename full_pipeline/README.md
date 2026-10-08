# PennCNV + CNValidatron

A configurable pipeline for calling copy-number variants (CNVs) from SNP-array
signals with PennCNV and classifying those calls with CNValidatron. Samples are
listed in a tab-separated manifest; input paths, reference files, genome builds,
processing batches and QC thresholds are defined in one YAML configuration.

For each batch, the pipeline prepares signals, generates a population B-allele
frequency (PFB) file, optionally adjusts LRR for genomic waves, calls and filters
CNVs, merges adjacent calls, removes calls overlapping excluded regions, and
runs the trained CNValidatron model. Batches run sequentially; validation can use
multiple R workers within a batch. Bash entry points coordinate Python, Perl and
R scripts.

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

## Quick start

Run these commands from the repository root, `CNV_array_validation/`.
**Mamba must already be installed and available on your PATH.** Setup needs
internet access to download software and packages.

```bash
# Install the complete analysis environment, including PennCNV.
bash setup/setup_environment.sh
conda activate penncnv-cnvalidatron

# Check the supplied example configuration and dependencies.
bash full_pipeline/examples/run_example.sh --model /path/to/joint.rds --check

# Analyze the example data.
bash full_pipeline/examples/run_example.sh --model /path/to/joint.rds
```

Replace `/path/to/joint.rds` with your downloaded compatible model (see
[Inputs needed to run](#inputs-needed-to-run)). The example contains **three
fully simulated samples** on chromosome 22, with 7,959 probes per sample. It
includes independently generated LRR/BAF values, public probe metadata, a
manifest and a chromosome-22 GC reference. No participant signal values or
genotypes are included. `simdup` has an injected duplication, `simdel` an
injected deletion, and `simnormal` no injected event. Simulation truth is in
`examples/simulated/truth.tsv`; model predictions are generated when you run it.

Results are written to `full_pipeline/examples/simulated/results/example/`. The main result
is `cnvalidatron/results/final_predictions.tsv`. **Adjusted signals are generated
outputs**, under `prepared_signals/`; supply raw signals to the full pipeline.
This toy dataset tests execution and is not an accuracy benchmark for the model.
See the [simulation details](examples/simulated/README.md).

Each run needs a **new output directory**. To rerun the example, select another
output directory with `--output`, which is relative to your current working
directory:

```bash
bash full_pipeline/examples/run_example.sh --model /path/to/joint.rds \
  --output full_pipeline/examples/simulated/results_02
```

Existing output directories are rejected, including during `--check`; the
pipeline does not overwrite results or resume an interrupted run. The example
script passes your model and output paths to the regular pipeline without
editing the distributed configuration.

Setup creates or updates the `penncnv-cnvalidatron` environment using mamba,
installs CPU Torch and the R dependencies, compiles PennCNV 1.0.5, and checks
package loading, a Torch calculation and command-line tools. PennCNV is
installed at `$CONDA_PREFIX/opt/PennCNV-1.0.5`. Torchvision is pinned to 0.6.0
and CNValidatron to commit `c436bc0a69f19950e7357d9c0459af4950e97088`;
the other environment dependencies are not fully locked.

## Inputs needed to run

For a real analysis, collect the following data and resources before editing the
configuration. The setup script installs software; it does **not** download your
study data, whole-genome GC reference or trained model. Exclusion lists are
included under `resources/`.

| Input | What you need | Included / where to obtain it |
|---|---|---|
| **Sample signal files** | One tab-separated file per sample, containing probe name, chromosome, position, LRR (`Log R Ratio`) and BAF (`B Allele Freq`). These are measured array intensities, not genotype calls alone. | Supply your own array exports, for example from GenomeStudio or your array-processing workflow. The [PennCNV input guide](https://penncnv.openbioinformatics.org/en/latest/user-guide/input/) describes signal preparation. A PLINK genotype fileset alone does not supply LRR/BAF. |
| **Sample manifest** | A tab-separated list linking `sample_id`, `batch` and `signal_file`. | Copy the included [manifest template](metadata/samples.example.tsv) and fill it with your sample information; no external download is needed. |
| **QC SNP BIM, per batch** | A six-column `.bim` listing probes retained by your upstream SNP QC, in the same build as the signals. | Obtain it from your study's QC-filtered PLINK dataset. It is study-specific, not a generic reference to download. See the [PLINK BIM format](https://www.cog-genomics.org/plink/2.0/formats#bim). Only the BIM is read here; `.bed` and `.fam` are not required. Set `qc_bim: null` to explicitly skip this filtering. |
| **GC reference** | The UCSC `gc5Base` database table used by PennCNV to calculate a batch-specific GC model. Supply it uncompressed and sorted by chromosome and start position. | A whole-genome reference is not bundled. For hg19, download [UCSC gc5Base.txt.gz](https://hgdownload.soe.ucsc.edu/goldenPath/hg19/database/gc5Base.txt.gz) from the [hg19 database directory](https://hgdownload.soe.ucsc.edu/goldenPath/hg19/database/), then prepare it as shown below. |
| **Excluded regions** | A study-approved, matching-build file of problematic intervals, with headerless tab-separated `chr:start-end` and annotation columns. | Included: [hg19 original intervals](resources/excluded_regions.hg19.original.tsv) and [hg38 original intervals](resources/excluded_regions.hg38.original.tsv). The template uses the hg19 list. Choose the list matching your signal build; no external download is needed. See [resource provenance](resources/README.md#included-exclusion-lists). |
| **CNValidatron trained model** | A compatible pretrained model file to load with `luz::luz_load`; set its path in `references.cnvalidatron_model`. | Not bundled or installed by setup. The authors provide the model through [Zenodo, DOI 10.5281/zenodo.17174637](https://doi.org/10.5281/zenodo.17174637), linked from their [pretrained-model documentation](https://github.com/SinomeM/CNValidatron_fl#pre-trained-model). Download the model file from that record and use its actual saved filename in the configuration. |

For hg19, the following commands download and prepare the GC table. Run them
from the repository root; they use `wget`, `gzip`
and `sort` from your shell environment:

```bash
mkdir -p full_pipeline/resources/hg19
wget -O full_pipeline/resources/hg19/gc5Base.txt.gz \
  https://hgdownload.soe.ucsc.edu/goldenPath/hg19/database/gc5Base.txt.gz
gzip -dc full_pipeline/resources/hg19/gc5Base.txt.gz \
  | LC_ALL=C sort -k2,2 -k3,3n \
  > full_pipeline/resources/hg19/gc5Base.sorted.txt
```

Then set `references.gc_file: ../resources/hg19/gc5Base.sorted.txt` in
`full_pipeline/config/config.yaml`. This pipeline expects the **database table**, not the
similarly named variableStep wiggle file in UCSC's separate `gc5Base/` directory.
For another genome build, obtain a compatible GC table for that build; do not
reuse the hg19 file. The current preflight requires a GC reference even with
`adjust_lrr: false`.

**Signals, QC BIM, GC reference and excluded regions must all match the declared
genome build.** No coordinate conversion is performed. Use whole-genome resources
for a whole-genome analysis; the example's chromosome-22 resources are for its
small test only.

You do not need to supply a PFB, GC model, CNV-call table, compressed/indexed
validation signals or CNValidatron SNP/sample tables: the pipeline generates
these. PennCNV's `lib/hhall.hmm` is supplied by the PennCNV installation.

The distributed example under `examples/simulated/` includes only synthetic
signals and genomic references. Its reproducible generator reads probe
coordinates and generates new values; it never reads participant signals.
Configuration and manifest templates are also included. The trained model
remains a separate download.

## Set up a real run

Copy the templates, then edit the copies:

```bash
cp full_pipeline/config/config.example.yaml full_pipeline/config/config.yaml
cp full_pipeline/metadata/samples.example.tsv full_pipeline/metadata/samples.tsv
```

In **`full_pipeline/config/config.yaml`**, replace the `/path/to/...` placeholders with your
new output directory, GC reference, trained model and per-batch QC BIM. Check
that the included exclusion list matches your genome build. Set the genome-build labels, add your batch definitions, and choose the
worker count and QC settings described below. Leave `tools.penncnv_dir: null`
to use PennCNV from the activated environment.

In **`full_pipeline/metadata/samples.tsv`**, list your sample IDs, batch names and signal-file
paths. Batch names must match entries under `batches` in the YAML. Include only
samples you intend to analyze after your upstream sample QC. Each batch should
contain compatible array/probe sets; PFB is calculated separately for each batch.

```text
sample_id	batch	signal_file
sample001	batch_A	/path/to/sample001.txt
sample002	batch_A	/path/to/sample002.txt
```

Save this as a **tab-separated** file. Sample IDs may contain letters, digits
and hyphens; underscores and periods are unsupported by the validation worker.
IDs must be unique within each batch. Batch names may additionally contain
underscores.

Configuration paths are resolved relative to the **YAML file**. Signal paths
are resolved relative to the **manifest file**. Absolute paths are supported;
`~` is expanded, but shell variables such as `$HOME` are not expanded in YAML.
Keep the output directory path free of whitespace.

**All coordinate inputs must already use the same genome build. No liftover
is performed.** Build labels are checked for consistency, but they cannot verify
a file's actual coordinates. See [reference formats](resources/README.md).

Once configured:

```bash
conda activate penncnv-cnvalidatron
bash full_pipeline/run_pipeline.sh --config full_pipeline/config/config.yaml --check
bash full_pipeline/run_pipeline.sh --config full_pipeline/config/config.yaml
```

### Required input formats

| Input | Required format |
|---|---|
| Per-sample signal | Tab-separated columns `Name`, `Chr`, `Position`, `Log R Ratio`, `B Allele Freq`; optional `GType`. Signal columns may have a sample prefix, such as `sample001.Log R Ratio`. |
| QC SNP list | Six-column PLINK BIM in the signal genome build. Filtering matches chromosome and position. Set `qc_bim: null` to explicitly skip this filtering. |
| GC reference | Uncompressed PennCNV GC reference matching the signal genome build. Currently required even when wave adjustment is disabled. |
| Excluded regions | Headerless, tab-separated locus and annotation: `chr:start-end` followed by the annotation, as expected by PennCNV `scan_region.pl`. |
| Trained model | Compatible model loaded with `luz::luz_load`, such as `joint.rds`. Setup installs software, not the trained model. |

Positions must be positive, 1-based integers. Preparation removes `chr`
prefixes, drops rows missing probe names or coordinates, retains the first row
at duplicate positions, and normalizes column order. If `GType` is absent,
`NC` is written. After filtering, probe names, coordinates and row order must
agree across samples within a batch or the run stops before PFB calculation.
CNValidatron preparation retains numeric chromosome labels; named sex
chromosomes are unsupported in this version.

### Configuration parameters

| YAML key | Meaning / template default |
|---|---|
| `output_dir` | New directory for all results; must not already exist. |
| `samples_manifest` | Path to the tab-separated sample manifest. |
| `signal_genome_build` | Signal coordinate build, for example `hg19`. |
| `adjust_lrr` | `true`: apply PennCNV GC wave adjustment; `false`: use unadjusted LRR. |
| `workers` | Maximum concurrent validation workers; template uses `4`. |
| `tools.penncnv_dir` | `null`: use the active environment's `opt/PennCNV-1.0.5`; otherwise an explicit installation path. |
| `tools.rscript` | R executable; normally `Rscript` from the active environment. |
| `tools.validation_script` | Shared `../cnvalidatron_wrapper/bin/validation_CNV.r`, relative to `full_pipeline/`; the template supplies the correct path. |
| `references.gc_file` / `gc_genome_build` | GC reference path and its genome build. |
| `references.excluded_regions` / `excluded_regions_genome_build` | Exclusion file path and its genome build. |
| `references.cnvalidatron_model` | Trained model path. |
| `batches.<name>.qc_bim` / `qc_genome_build` | Batch-specific QC BIM and coordinate build. |
| `batches.<name>.min_input_snps` | Minimum usable input rows before SNP QC filtering and duplicate removal; `0` disables this sample filter. |
| `batches.<name>.common_snps_only` | `true`: intersect positions across accepted samples before filtering; default `false`. Probe names must still agree. |

QC settings are under `qc`:

| Key | Default | Purpose |
|---|---:|---|
| `lrr_sd` | 0.3 | PennCNV sample QC threshold for LRR standard deviation. |
| `baf_drift` | 0.01 | Sample QC threshold for BAF drift. |
| `wave_factor` | 0.05 | Sample QC threshold for wave factor. |
| `min_snps` | 10 | Minimum SNP count per CNV. |
| `min_length_bp` | 50000 | Minimum CNV length in base pairs. |
| `merge_fraction` | 0.2 | Fraction passed to `clean_cnv.pl combineseg`. |
| `excluded_region_overlap` | 0.5 | Minimum query overlap fraction passed to `scan_region.pl`. |

These values are configurable defaults; review them for your array and study.
The model supplies the CNValidatron classifications and probabilities; this
pipeline does not apply an additional probability cutoff.

## Commands and options

### Environment setup

```bash
bash setup/setup_environment.sh [--name ENV] [--install-penncnv | --skip-penncnv]
```

| Option | Behavior |
|---|---|
| `--name ENV` | Create or update another environment name; default `penncnv-cnvalidatron`. Activate that name for analysis. |
| `--install-penncnv` | Install PennCNV; this is the default. |
| `--skip-penncnv` | Skip PennCNV installation. Set `tools.penncnv_dir` if using an existing installation elsewhere. |
| `--help` | Show setup usage. |

The R setup files are called automatically in separate processes to install the
Torch runtime, install remaining packages, and verify loading. They do not need
to be run manually for normal setup.

To install or repair PennCNV separately, activate the target environment first:

```bash
bash setup/install_penncnv.sh
# Use a downloaded official v1.0.5 archive instead of downloading it again:
bash setup/install_penncnv.sh --source-archive /path/to/v1.0.5.tar.gz
# Confirm the installed program loads:
perl "$CONDA_PREFIX/opt/PennCNV-1.0.5/detect_cnv.pl" --help
```

The installer checks whether the existing Perl extension loads and rebuilds it
when needed. Compilation diagnostics are saved in the installation directory
as `installation.log`.

### Simulated example

```bash
bash full_pipeline/examples/run_example.sh --model MODEL.rds [--output NEW_DIRECTORY] [--check]
```

`--model` is required; `--output` selects a fresh result directory (default
`examples/simulated/results`); `--check` performs the regular pipeline preflight;
`--help` shows usage. To regenerate the supplied raw synthetic signals and truth
from the fixed seed:

```bash
python full_pipeline/examples/simulated/generate_signals.py
```

This regeneration overwrites only the synthetic signal files and `truth.tsv`;
it does not generate adjusted signals or analysis results.

### Pipeline execution

```bash
bash full_pipeline/run_pipeline.sh --config CONFIG.yaml [--batch NAME] [--check]
```

| Option | Behavior |
|---|---|
| `--config CONFIG.yaml` | Required configuration path. |
| `--batch NAME` | Select one batch from the manifest; otherwise process all listed batches. |
| `--check` | Check configuration, manifest, input-file existence, executables, PennCNV extension and R package loading without writing outputs. It does not read every signal row or load the trained model. |
| `--help` | Show pipeline usage. |

Example: check just one batch before running it:

```bash
bash full_pipeline/run_pipeline.sh --config full_pipeline/config/config.yaml --batch batch_A --check
bash full_pipeline/run_pipeline.sh --config full_pipeline/config/config.yaml --batch batch_A
```

The Python stage modules in `bin/` are invoked by this entry point; they are not
separate command-line tools.

### Optional SLURM submission

Activate the analysis environment before submitting. Request at least as many
CPUs as `workers`, and supply your site's memory, time and partition options:

```bash
sbatch --cpus-per-task=4 full_pipeline/profiles/slurm/submit_pipeline.sh \
  /absolute/path/to/full_pipeline /absolute/path/to/config.yaml
# Append a batch name to submit only that batch.
```

The wrapper limits common numerical-library thread counts to one per process.
SLURM is optional; the regular entry point runs directly in your environment.

## Outputs

```text
<output_dir>/
├── config.resolved.yaml                # Configuration with resolved paths
└── <batch>/
    ├── sample_qc.tsv                   # Input SNP counts and acceptance status
    ├── prepared_samples.tsv           # Accepted samples and prepared signal paths
    ├── prepared_signals/              # Normalized signals and optional adjusted files
    ├── penncnv.commands.log            # PennCNV commands and diagnostics
    ├── penncnv/
    │   ├── probes.pfb                  # Batch-specific PFB
    │   ├── gcmodel.txt                 # Present when LRR adjustment is enabled
    │   ├── step0.rawcnv                # Raw calls
    │   ├── step0.log                   # Detection/sample QC diagnostics
    │   ├── step1.qcsum                 # PennCNV sample QC summary
    │   ├── step1.qcpass                # Samples passing PennCNV QC
    │   ├── step1.goodcnv               # QC-filtered calls
    │   ├── step2_merged.goodcnv         # Merged calls
    │   └── step3.goodcnv.excludeBadRegions # Calls retained after region exclusion
    └── cnvalidatron/
        ├── signals/                   # Validation signal tables
        ├── indexed_signals/           # bgzip signals and tabix indexes
        ├── snps.tsv
        ├── samples.tsv
        ├── cnvs.tsv                   # Retained calls in validation format
        └── results/
            ├── worker_*/              # Worker inputs, logs and predictions
            └── final_predictions.tsv  # Combined CNValidatron predictions
```

`final_predictions.tsv` contains sample IDs, chromosome/start/end, copy number,
SNP counts, predicted class and class probabilities. Validation skips samples
with no retained calls, so this is a **CNV-level table**, not a list of all
samples. A batch without retained CNVs receives a header-only predictions file.
Worker failures stop the run and leave logs for inspection.

## Checks and code layout

```bash
python -m unittest discover -s full_pipeline/tests -v
```

Tests cover input preparation, configuration checks, CNV parsing, worker failure
handling and setup/installer behavior. Some external commands are mocked;
these tests complement the small example run and do not establish full-cohort
calling accuracy or equivalence to another workflow.

`config/` and `metadata/` hold the editable templates; the repository-root
`setup/` contains the shared environment specification and installers; `bin/`
contains the processing stages;
`resources/` documents reference requirements; `examples/` contains example
usage; and `profiles/slurm/` provides optional scheduler submission.

The pipeline invokes the shared worker at
`../cnvalidatron_wrapper/bin/validation_CNV.r`. It preserves sample IDs as
character values, including leading zeros. The worker and pipeline integration
are described in the [wrapper README](../cnvalidatron_wrapper/README.md).
