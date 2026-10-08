# Expected format after preparation

The three `*_ready.txt` files describe the prepared input tables for the raw
synthetic example in [before_preparation/](../before_preparation/README.md).
They are static reference inputs, not model predictions or generated run results.

| Reference file | Corresponding actual output |
|---|---|
| `samples_ready.txt` | `generated/samples.tsv`; sample IDs and plain/indexed signal paths. |
| `snps_ready.txt` | `generated/snps.tsv`; the raw SNP table with `Index` removed. |
| `cnvs_ready.txt` | `generated/cnvs.tsv`; the raw calls parsed into validation columns. |

The reference sample table uses portable relative paths under `generated/`.
Actual preparation writes absolute paths based on your machine. Once the
preparation command in the linked README has run, both sets of paths identify
the same signal files when resolved relative to their sample tables.

Prepared signal tables have columns `Chr`, `Start`, `End`, `Log R Ratio`,
`B Allele Freq`, `Log R Ratio Adjusted`, are sorted by chromosome and position,
and have bgzip-compressed copies and `.tbi` indexes. For this raw synthetic
example, `End` equals `Start` and the adjusted-LRR column equals the supplied
LRR; no wave correction is performed by preparation.

Only expected-format references are stored here. Users generate the signal
copies/indexes and actual prepared tables by running preparation. The
`generated/` directory is ignored by Git and is not included in the repository.

## Upstream credit

CNValidatron and its pretrained model were developed by **Simone Montalbano
(SinomeM) and collaborators**. This example/resource supports the wrapper and
pipeline around their [original CNValidatron software](https://github.com/SinomeM/CNValidatron_fl/tree/main).
Please cite the [CNValidatron publication](https://doi.org/10.1186/s12859-026-06375-6)
when using their software/model.
