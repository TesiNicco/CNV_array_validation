# References and trained model

Supply reference/model paths in configuration. The exclusion lists described
below are included; the whole-genome GC reference and trained model are external.

- `gc_file`: uncompressed PennCNV GC reference for the signal genome build.
- `excluded_regions`: headerless, tab-separated `chr:start-end` and annotation,
  for that same genome build, in the format expected by `scan_region.pl`.
- `cnvalidatron_model`: the compatible trained model loaded by `luz::luz_load`,
  such as the `joint.rds` model used in the existing analysis.
- `qc_bim`: optional per-batch PLINK BIM already using signal-build coordinates.

Genome build labels are mandatory and checked for consistency. The pipeline does
not transform coordinates or generate exclusion regions. A label is a user's
declaration, not proof of a file's actual coordinate build. Verify each source.

## Included exclusion lists

- `excluded_regions.hg38.original.tsv`: exact copy of the list referenced by
  the original calling script, sourced from
  `Regions_toremove_hg38_20251106_locus_annotation.txt`. Its coordinates were
  preserved without edits.
- `excluded_regions.hg19.original.tsv`: full list prepared from the existing
  `Regions_toremove_hg38_20260107_locus_annotation_GRCh37.txt` table. Despite
  its source filename, that table declares GRCh37 coordinates. The original
  `chromStart` and `chromEnd` columns were used; the start was increased by one
  to convert BED coordinates to PennCNV's inclusive locus format. Enlarged
  interval columns were not used and no liftover was performed. Its chr22 rows
  exactly match the tested example exclusion file.

These are separately sourced lists, not a claim of equivalent intervals across
builds. They contain centromere, telomere and immunoglobulin-region annotations.
Use the file matching your inputs and review its suitability for your analysis.
The generic hg19 configuration points to `excluded_regions.hg19.original.tsv`.
Source filenames, checksums and preparation details are recorded in
[excluded_regions.provenance.json](excluded_regions.provenance.json).

Both files are headerless, tab-separated `chr:start-end` and annotation tables
for PennCNV `scan_region.pl`; they are not standard BED files. To use a different
study-approved exclusion list, supply its path and matching build in the YAML.

## Upstream credit

CNValidatron and its pretrained model were developed by **Simone Montalbano
(SinomeM) and collaborators**. This example/resource supports the wrapper and
pipeline around their [original CNValidatron software](https://github.com/SinomeM/CNValidatron_fl/tree/main).
Please cite the [CNValidatron publication](https://doi.org/10.1186/s12859-026-06375-6)
when using their software/model.
