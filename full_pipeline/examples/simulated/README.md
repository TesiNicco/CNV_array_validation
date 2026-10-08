# Simulated chromosome-22 example

Three synthetic samples share 7,959 hg19 array probe coordinates:

| Sample | Injected event |
|---|---|
| `simdup` | Copy number 3 between chr22:30,000,000–30,700,000 |
| `simdel` | Copy number 1 between chr22:36,000,000–36,400,000 |
| `simnormal` | Copy number 2 throughout |

`signals/*.chr22.tsv` are **raw synthetic inputs**. The generator uses a fixed
seed of 20261008, synthetic per-probe allele frequencies between 0.25 and 0.75,
independently sampled allele dosages, and Gaussian measurement noise. Mean LRR
is 0 for copy number 2, −0.50 for deletion and 0.32 for duplication; its standard
deviation is 0.065. BAF is dosage divided by copy number plus noise with standard
deviation 0.012, clipped to [0, 1]. `GType` is `NC` and contains no measured
genotypes. These simple assumptions make a reproducible execution example;
they do not model all characteristics of real array data.

Probe identifiers and coordinates are retained from existing array metadata;
no participant IDs, signal values, genotypes or CNV calls are copied. The
injected event intervals were chosen for this simulation. See
[provenance.json](provenance.json) for reference checksums and simulation details.

## Files

- `signals/`: generated raw LRR/BAF for the three samples.
- `samples.tsv`: sample-to-signal manifest.
- `config.yaml`: portable pipeline configuration; trained model path is external.
- `reference/qc_snps.hg19.bim`: probe names and positions; unused alleles are 0/0.
- `reference/hg19.chr22.gc5Base.txt`: chromosome-22 genomic GC reference.
- `truth.tsv`: injected regions, affected probe boundaries and counts; simulation
  ground truth, not PennCNV or model predictions.
- `generate_signals.py`: standalone reproducible generator, using Python's
  standard library and reading only the BIM probe metadata.

The configuration uses the included full hg19 exclusion list. Software and the
compatible trained CNValidatron model are installed/downloaded separately.

## Run

From the repository root:

```bash
conda activate penncnv-cnvalidatron
bash full_pipeline/examples/run_example.sh --model /path/to/joint.rds --check
bash full_pipeline/examples/run_example.sh --model /path/to/joint.rds
```

The model argument is an actual path to your compatible trained model. Results
appear under `examples/simulated/results/example/`. To use another fresh output
location, pass `--output NEW_DIRECTORY`; paths supplied on the command line are
relative to your current working directory. No results are distributed.

With `adjust_lrr: true`, PennCNV `genomic_wave.pl -adjust` generates adjusted
signals in the result directory before CNV calling. There is no precomputed
`adjusted_signals/` input folder in this example. The generator does not run
PennCNV or CNValidatron.

The injected events give a target for checking CNV calling, but exact inferred
boundaries, extra calls and model classes/probabilities may depend on the tools
and trained model. A successful run on this toy data does not measure accuracy
on real participants.

## Regenerate the raw inputs

```bash
python full_pipeline/examples/simulated/generate_signals.py
```

This overwrites the three synthetic signals and truth table using the fixed
seed. It does not change references, configuration or existing run results.

## Verified example behavior

A full run with PennCNV 1.0.5 and the existing compatible trained model retained
exactly the two injected CNVs, with boundaries at the first and last affected
probes listed in `truth.tsv`. CNValidatron classified them as duplication and
deletion; the normal sample had no calls. All three samples passed PennCNV QC.
The run used the default adjusted-LRR configuration. Prediction probabilities
may differ with another model or environment. Generated results are not included.

## Upstream credit

CNValidatron and its pretrained model were developed by **Simone Montalbano
(SinomeM) and collaborators**. This example/resource supports the wrapper and
pipeline around their [original CNValidatron software](https://github.com/SinomeM/CNValidatron_fl/tree/main).
Please cite the [CNValidatron publication](https://doi.org/10.1186/s12859-026-06375-6)
when using their software/model.
