# Runnable validation-only example

This example supplies three independently simulated chromosome-22 signal tables
and two fixed CNV calls. It runs CNValidatron through the shared validation
worker without installing or running PennCNV. All coordinates use hg19.

## Run

From the repository root, after creating and activating the shared environment:

```bash
bash setup/setup_environment.sh --skip-penncnv
conda activate penncnv-cnvalidatron
bash cnvalidatron_wrapper/example_data/run_example.sh --model /path/to/joint.rds --check
bash cnvalidatron_wrapper/example_data/run_example.sh --model /path/to/joint.rds
```

Skip the setup command if the working environment already exists. Replace the
model path with your compatible pretrained model, available through the authors'
[Zenodo model record](https://doi.org/10.5281/zenodo.17174637). The model is external
and is not downloaded by this example.

`--check` checks input-file existence, bgzip/tabix/Rscript and R package loading
without writing outputs or loading the trained model. Use `--output NEW_DIRECTORY`
to select another fresh output directory, relative to your current working
directory. The default is `cnvalidatron_wrapper/example_data/simulated/results`.
Existing output directories are rejected. `--help` shows available options.

## Inputs supplied

| Input | Purpose |
|---|---|
| `signals/simdup.tsv` | Synthetic intensities containing an injected duplication. |
| `signals/simdel.tsv` | Synthetic intensities containing an injected deletion. |
| `signals/simnormal.tsv` | Synthetic normal control, with no corresponding CNV call. |
| `samples.tsv` | Portable sample IDs and relative signal-file paths. |
| `snps.tsv` | Names, chromosomes and positions of the 7,959 probes. |
| `cnvs.tsv` | Two fixed calls derived from the injected simulation truth; these are validation inputs, not predictions. |
| `provenance.json` | Generation details and file checksums. Not read by the analysis. |

The signal files have validation-ready columns `Chr`, `Start`, `End`,
`Log R Ratio`, `B Allele Freq`, and `Log R Ratio Adjusted`. They derive from the
same synthetic inputs as the full-pipeline example, but this folder is
self-contained and does not read files from `full_pipeline/`.

**No wave adjustment is performed here.** For these toy inputs,
`Log R Ratio Adjusted` equals the raw synthetic LRR. This makes the signals
compatible with the worker's input format; it does not mean they were corrected
by PennCNV. There are no participant measurements, genotypes or sample IDs.

The supplied calls are chr22:30,048,182–30,695,372 (CN 3, 91 SNPs) and
chr22:36,002,985–36,377,903 (CN 1, 59 SNPs). They are fixed inputs, so this
example tests validation independently of CNV calling and GC adjustment.

## Generated outputs

The example copies signals into the new output directory, compresses them with
bgzip, creates tabix indexes, writes a sample manifest with resolved paths, and
passes the SNP/sample/CNV tables to `bin/validation_CNV.r` in this wrapper.

```text
<output>/
├── signals/              # Signal copies, .gz files and .tbi indexes
├── samples.tsv           # Generated absolute paths to the indexed signals
├── snps.tsv
├── cnvs.tsv
├── commands.log          # Commands and preparation/worker diagnostics
└── validation/
    ├── pngs/             # Images used for predictions
    └── predictions.txt   # CNValidatron results
```

Expect two prediction rows, for `simdup` and `simdel`. `simnormal` has no CNV
input, so it has no prediction row. The model supplies classes and probabilities;
this toy example is not an accuracy benchmark. The default result directory is ignored
by Git; generated results are not distributed.

## Upstream credit

CNValidatron and its pretrained model were developed by **Simone Montalbano
(SinomeM) and collaborators**. This example/resource supports the wrapper and
pipeline around their [original CNValidatron software](https://github.com/SinomeM/CNValidatron_fl/tree/main).
Please cite the [CNValidatron publication](https://doi.org/10.1186/s12859-026-06375-6)
when using their software/model.
