# Raw synthetic inputs for preparation

This is a runnable example of the format **before preparation**, containing
three synthetic hg19 chromosome-22 samples and two fixed simulated CNV calls.
No participant signal values, genotypes or sample IDs are included.

| File | Content |
|---|---|
| `signals/simdup.tsv` | Raw synthetic LRR/BAF with an injected duplication. |
| `signals/simdel.tsv` | Raw synthetic LRR/BAF with an injected deletion. |
| `signals/simnormal.tsv` | Raw synthetic normal control. |
| `samples.txt` | Tab-separated `sample_ID`, `file_path`; paths are relative to this manifest. |
| `snps.txt` | Tab-separated `Index`, `Name`, `Chr`, `Position`; preparation removes `Index`. |
| `cnvs.txt` | Raw PennCNV-format records constructed from simulation truth; signal paths match the manifest. These are simulated input calls, not outputs of PennCNV or CNValidatron. |
| `provenance.json` | Simulation seed and input checksums; not used by the analysis. |

The raw signals contain `Name`, `Chr`, `Position`, `GType`, `Log R Ratio` and
`B Allele Freq`. They have no precomputed adjusted-LRR column. Preparation does
not perform wave correction: it copies the supplied synthetic LRR into the
validation-format adjusted column.

## Prepare these files

From the repository root, with `penncnv-cnvalidatron` activated:

```bash
Rscript cnvalidatron_wrapper/bin/preparation.R \
  --samples cnvalidatron_wrapper/example_data/before_preparation/samples.txt \
  --snps cnvalidatron_wrapper/example_data/before_preparation/snps.txt \
  --cnvs cnvalidatron_wrapper/example_data/before_preparation/cnvs.txt \
  --cnv-format penncnv \
  --outdir cnvalidatron_wrapper/example_data/after_preparation/generated
```

Add `--check` to validate the inputs without writing outputs. The selected
output directory must not exist, even during `--check`. For a repeat run, use a
new directory with `--outdir`.

The outputs include `samples.tsv`, `snps.tsv`, `cnvs.tsv` and the formatted,
compressed and indexed signal files. Compare their schemas with the
[after-preparation references](../after_preparation/README.md). Generated files
are ignored by Git and are not distributed.

## Validate the prepared calls

After running preparation above, supply the downloaded compatible model:

```bash
Rscript cnvalidatron_wrapper/bin/parallelize_validation.r \
  --samples cnvalidatron_wrapper/example_data/after_preparation/generated/samples.tsv \
  --snps cnvalidatron_wrapper/example_data/after_preparation/generated/snps.tsv \
  --cnvs cnvalidatron_wrapper/example_data/after_preparation/generated/cnvs.tsv \
  --model /path/to/joint.rds \
  --outdir results/validated_from_raw \
  --workers 2
```

Expect prediction rows for `simdup` and `simdel` in
`results/validated_from_raw/final_predictions.txt`; the normal control has no
input call. This preparation example and the validation-ready dataset in
`../simulated/` use the same synthetic values. Neither requires PennCNV.

## Upstream credit

CNValidatron and its pretrained model were developed by **Simone Montalbano
(SinomeM) and collaborators**. This example/resource supports the wrapper and
pipeline around their [original CNValidatron software](https://github.com/SinomeM/CNValidatron_fl/tree/main).
Please cite the [CNValidatron publication](https://doi.org/10.1186/s12859-026-06375-6)
when using their software/model.
