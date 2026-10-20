# Allele-level variant comparison

This section supports the manuscript comparison between the Parabricks-derived call set and the GIAB DRAGEN hard-filtered comparator. Files 01–04 and 06 are copied unchanged from `HG008-BCFtools-Parabricks-vs-DRAGEN`; the complete original repository, including its original README, is preserved in [provenance](../../provenance/README.md).

**Preparation correction:** the original `05_compare_indels.py` actually contained a summary-table builder, not an indel comparison. Its original bytes remain in the source snapshot. The active file 05 is a newly reconstructed exact-allele set comparison, with insertion/deletion summaries and no-overwrite output behavior. It has been tested on synthetic inputs only, not rerun on historical HG008 data. Do not present it as the original executed script or claim manuscript counts have been reproduced by this correction.

## Inputs and counting unit

- Parabricks: the final **PASS-filtered, positive-TLOD** VCF, not the raw MutectCaller file and not the optimized RTG-thresholded file.
- DRAGEN: `dragen_4.2.4_HG008-mosaic_tumor.hard-filtered.vcf.gz`, using PASS records.
- Exclude symbolic ALT entries according to the historical preparation script.
- Matching key: `CHROM,POS,REF,ALT`. The Python extraction splits multiallelic ALT entries into individual alleles and uses sets. It does not perform haplotype-aware matching or silently normalize representations.
- SNV: REF and ALT length 1; indel: unequal lengths; equal lengths greater than 1 are classified as OTHER. OTHER entries are not included in the manuscript's SNV+indel total.

VCF record counts, extracted allele counts, SNV+indel counts and RTG haplotype-aware counts are different quantities. The 17,455 full-run VCF records must not be substituted for the manuscript's 17,134 SNVs+indels without repeating and checking the classification.

## Preserved preparation scripts

`01_prepare_pass_vcfs.sh` and `02_run_bcftools_stats.sh` are retained unchanged. They require `bcftools`/`plot-vcfstats` on PATH and take explicit input/output arguments. Preparation itself does **not** enforce positive TLOD; supply the already selected Parabricks PASS_TLOD file. The manuscript records BCFtools 1.24 for its comparative statistics; the new Nextflow's BCFtools 1.21 is a separate environment. Do not silently rewrite one version as the other.

From this directory, using new output directories:

```bash
bash 01_prepare_pass_vcfs.sh /path/to/parabricks.PASS_TLOD.vcf.gz /path/to/dragen.vcf.gz /path/to/comparison/01_prepared
bash 02_run_bcftools_stats.sh /path/to/comparison/01_prepared/clara.pass.nonsymbolic.vcf.gz /path/to/comparison/01_prepared/dragen.pass.nonsymbolic.vcf.gz /path/to/comparison/02_stats
python3 03_extract_variant_sets.py /path/to/comparison/01_prepared/clara.pass.nonsymbolic.vcf.gz /path/to/comparison/01_prepared/dragen.pass.nonsymbolic.vcf.gz /path/to/comparison/03_sets
python3 04_compare_snvs.py /path/to/comparison/03_sets/clara/snvs.tsv /path/to/comparison/03_sets/dragen/snvs.tsv /path/to/comparison/04_snvs
python3 05_compare_indels.py /path/to/comparison/03_sets/clara/indels.tsv /path/to/comparison/03_sets/dragen/indels.tsv /path/to/comparison/05_indels
python3 06_build_summary_table.py /path/to/comparison/04_snvs/summary.txt /path/to/comparison/05_indels/summary.txt /path/to/comparison/06_table
```

These are independent scripts, not an atomic no-overwrite workflow: several create/overwrite individual outputs. Always use a fresh output root. The shell preparation's record-level symbolic exclusion can remove an entire mixed multiallelic record; preserve the original rule for historical comparison rather than changing it without a separate analysis.

The Python scripts use the standard library. The repository tests exercise tiny synthetic examples, not the historical HG008 input files. VAF/FILTER characterization is a [separate section](../vaf/README.md) and is not implemented by these six scripts.
