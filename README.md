# CNV calling and validation workflows

This repository offers two workflows for SNP-array copy-number variants (CNVs).
Both use the same CNValidatron validation worker and shared analysis environment.

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
this repository's license is in [LICENSE](LICENSE).

## Choose your workflow

| Starting point | Workflow | Instructions |
|---|---|---|
| Existing PennCNV calls and their corresponding LRR/BAF signals | **CNValidatron wrapper:** prepare/index inputs if needed, then validate calls directly or in parallel. Does not run PennCNV. | [cnvalidatron_wrapper/README.md](cnvalidatron_wrapper/README.md) |
| Array LRR/BAF signals requiring CNV calling | **Full pipeline:** prepare signals, generate PFB/GC resources, optionally adjust LRR, call/filter/merge CNVs with PennCNV, then validate with CNValidatron. | [full_pipeline/README.md](full_pipeline/README.md) |

Existing calls alone are insufficient for validation: their signal files and
SNP/sample information are also required. All coordinate inputs must already
share a genome build; neither workflow performs liftover.

## Install the shared environment

Clone the repository and work from its root. Mamba must already be on your PATH;
setup downloads packages and requires internet access.

```bash
git clone https://github.com/TesiNicco/CNV_array_validation.git
cd CNV_array_validation
# Full workflow, including PennCNV:
bash setup/setup_environment.sh
conda activate penncnv-cnvalidatron
```

For validation only, use `bash setup/setup_environment.sh --skip-penncnv`
instead. Both options create the `penncnv-cnvalidatron` environment. Users with
an existing working environment can activate it without reinstalling.
The trained model is downloaded separately from the authors'
[Zenodo record](https://doi.org/10.5281/zenodo.17174637).

## Try the synthetic examples

With the environment activated, replace the model path below:

```bash
# Validate fixed synthetic calls without PennCNV:
bash cnvalidatron_wrapper/example_data/run_example.sh --model /path/to/joint.rds

# Run PennCNV calling and validation on raw synthetic signals:
bash full_pipeline/examples/run_example.sh --model /path/to/joint.rds
```

Both examples support `--check` and `--output NEW_DIRECTORY`. A new output
directory is required for each run. The examples contain only synthetic signals
and genomic references; users generate their own results. To test standalone
conversion of raw signals and raw CNV records, follow the
[before-preparation example](cnvalidatron_wrapper/example_data/before_preparation/README.md).

## Repository layout

```text
CNV_array_validation/
├── README.md
├── LICENSE
├── setup/                   # Shared mamba environment and software installers
├── cnvalidatron_wrapper/    # Preparation and validation of existing calls
└── full_pipeline/           # PennCNV calling followed by validation
```

The validation worker lives in `cnvalidatron_wrapper/bin/validation_CNV.r` and
is called by both workflows. Runtime outputs, caches and personal run
configurations are excluded from Git. Whole-genome GC references, study data
and the trained model are external resources described in the workflow READMEs.

## Verification

Run these checks in the activated environment:

```bash
python -m unittest discover -s cnvalidatron_wrapper/tests -v
python -m unittest discover -s full_pipeline/tests -v
```

Tests cover input conversion, indexing, worker failures, configuration and
setup behavior. Some tests substitute external workers or tools; the documented
synthetic runs also exercise the installed PennCNV and actual trained model.
Testing used a Linux environment. Fresh installation on another machine,
SLURM submission and whole-cohort scientific validation require their own checks.
The environment specification is not a fully locked dependency snapshot.

## Existing users

The previous top-level `bin/` and `example_data/` directories now live under
`cnvalidatron_wrapper/`. Preparation and the parallel launcher accept explicit
arguments; see their README or `--help`. Update existing command paths to the
new locations. The direct worker keeps its existing argument interface.
